# TODO: make this take a directory as an argument

import os, ffmpy, subprocess, logging, sys
TARGET_FOLDER = '/users/mgomez/Desktop/test/'
vid_extensions = {".flv",".rmvb",".divx",".ogm",".mkv",".mov",".avi",".wmv",".m4v",".mp4"}
sub_extensions = {".srt",".ssa",".sub"}

from logging import handlers
# Setup logging
log = logging.getLogger('')
log.setLevel(logging.INFO)
format=logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# STDout handler
sout = logging.StreamHandler(sys.stdout)
sout.setFormatter(format)
log.addHandler(sout)

# File handler
fhand = logging.FileHandler('./transcode.log')
fhand.setFormatter(format)
log.addHandler(fhand)

def mkvMerge(baseFolder = None, baseFileName = None):
    logging.debug('Entered call to mkvmerge')
    # We'll assume that the srt and mkv have the same file name
    #  Since this method is a pretty cheap one, we can call it from both
    #  the FFMPEG transcode and the srt rename, hopefully hitting on one of them
    srtPath = os.path.join(baseFolder, baseFileName + '.srt')
    mkvPath = os.path.join(baseFolder, baseFileName + '.mkv')
    tmpPath = os.path.join(baseFolder, baseFileName + '.tmp.mkv')

    log.debug('Checking if mkv and srt file exist for %s', baseFileName)
    if not os.path.isfile(srtPath) or not os.path.isfile(mkvPath):
        # no srt file
        log.error('Either srt or mkv do not exist for %s', baseFileName)
        return
    log.debug('srt and mkv both exist for %s', baseFileName)
    #Rename the existing file to a temp extension
    #  This way mkvmerge can use the 'real' name as the final destination
    #  making cleanup a lot easier
    log.debug('renaming %s to %s', mkvPath, tmpPath)
    os.rename(mkvPath, tmpPath)
    # Execute the merge (pull the subtitles into the mkv)
    try:
        mkvMergeCmd = "mkvmerge -o '{}' '{}' '{}'".format(mkvPath,tmpPath,srtPath)
        log.info('Attempting to merge srt %s with mkv %s into new file %s',srtPath,tmpPath, mkvPath)
        log.debug('Merge Command - %s', mkvMergeCmd)
        results = subprocess.check_call(mkvMergeCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log.info('Merge successful. cleaning up by removing tmp and srt files')
        # Remove the old files
        os.remove(srtPath)
        os.remove(tmpPath)
    except subprocess.CalledProcessError as e:
        log.error('Error during mkvmerge for %s ', mkvPath)
        log.debug('Renaming the temp file back due to error')
        os.rename(tmpPath,mkvPath)
    except:
        log.error('Unknown type of error. roll back by renaming the tmp file')
        os.rename(tmpPath,mkvPath)
    return

def processFolder(target = None):
    for root, dirs, files in os.walk(target):
        for name in files:
            # file name w/o extension
            filename = os.path.splitext(name)[0]
            # the extnesion itself (including the '.')
            ext = os.path.splitext(name)[1]
            #print "file: " + filename + "\next: " + ext

            if ext in vid_extensions:

                # Make sure we don't reencode things we've already encoded
                if not filename.endswith("-HEVC"):
                    sourceFullPath = os.path.join(root,name)
                    destFullPath = os.path.join(root, filename+" -HEVC.mkv")

                    log.info('Executing transcode for %s', sourceFullPath)

                    #If the job crashed in the middle of a transcode, delete the partially completed object
                    if os.path.isfile(destFullPath):
                        logging.warning('Destination already exists , this is probably due to a failed prior attempt. Deleting pre-existing destination. source: %s dest: %s', sourceFullPath, destFullPath)
                        os.remove(destFullPath)

                    # FFMPEG args and reason
                    #   -map 0 -c copy  <- this tells ffmpeg to copy everything over, very important for dual language files w/ subtitles
                    #   -c:v lib265 -preset medium -crf 24 <- use h265 medium preset (medium produces a filesize similar to slow but much faster) quailty rate 24
                    #   -c:a libfdk_aac -b:a 128k <- use libdfk's aac encoder (best quality encoder for mmpeg as of 8/29/16) w/ each channel at 128k bits
                    ff = ffmpy.FFmpeg(
                        inputs={sourceFullPath : None},
                        outputs={destFullPath : '-map 0 -c copy -c:v libx265 -preset medium -crf 24 -c:a libfdk_aac -b:a 128k'})

                    try:
                        #print so we know where we are (it makes me feel better being able to see the ffmpeg command)
                        #  also helpful for debug if ffmpeg crashes out
                        log.debug('FFMPEG command - %s', ff.cmd)
                        #Make the magic happen
                        ff.run()
                        log.info('Transcode complete for %s. Cleaning up', sourceFullPath)
                        log.debug('Deleting the original file')
                        #delete the original file
                        os.remove(os.path.join(root,name))
                        log.info('Calling mkvMerge to handle potential srt files')
                        log.debug('folder: %s filename: %s', root, filename)
                        mkvMerge(root, filename)
                    except:
                        # FFMPEG choked on something.
                        #  Log the error
                        log.error('FFMPEG failed for %s', sourceFullPath)
                else:
                    logging.info('Video file already HEVC ignoring %s', filename)

            elif ext in sub_extensions:
                logging.info('Found subtitle file, attempting to merge with applicable mkv %s', name)
                hevcName =""
                if not filename.endswith("-HEVC"):
                    logging.warning('sub file missing HEVC tail, renaming %s', name)
                    # rename the subtitle file to math the new name of the transcoded one
                    hevcName = filename + " -HEVC"
                    os.rename(os.path.join(root,name), os.path.join(root, hevcName + ext))
                else:
                    hevcName = filename
                # merge the srt and mkv (if applicable)
                mkvMerge(root, hevcName)

            else:
                # I don't know what you are, but get out of my library
                #No, seriously.  The library has some junk files from previous media managers
                #  e.g. ".cover" files or cover art jpgs.  We don't want those any more.
                unknownFile = os.path.join(root,name)
                log.info('unknown file type, deleting - %s', unknownFile)
                os.remove(unknownFile)
    return


processFolder(target = TARGET_FOLDER)
