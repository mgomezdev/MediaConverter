# TODO: make this take a directory as an argument

# External apps required:
# - ffmpeg (with lib-x265 and lib-faac enabled)

import ffmpy
import logging
import os
import sys
import subprocess
import json

# Constants
vid_extensions = {".flv",".rmvb",".divx",".ogm",".mkv",".mov",".avi",".wmv",".m4v",".mp4"}
sub_extensions = {".srt",".ssa",".sub",".idx"}
ONE_MB_IN_BYTES = 2 ** 20
ONE_GB_IN_BYTES = 2 ** 30

# arguments
TARGET_FOLDER = '/raid/video'
FORCE_CONVERSION_MIN_SIZE = ONE_GB_IN_BYTES
deleteUknown = True
logLevel = logging.INFO
hevcTag = " -HEVC"
staySafe = True 


# Setup logging
log = logging.getLogger('')
log.setLevel(logLevel)
format=logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# STDout handler
sout = logging.StreamHandler(sys.stdout)
sout.setFormatter(format)
log.addHandler(sout)

# File handler
fhand = logging.FileHandler('./transcode.log')
fhand.setFormatter(format)
log.addHandler(fhand)

def safeDelete(target):
    if os.path.isfile(target):
        os.remove(target)

def isHEVC(target = None):
    log.debug('Checking codecs for %s',target)
    FFPROBE_CMD = 'ffprobe'

    try:
      call_result = subprocess.check_output([FFPROBE_CMD, '-v', 'quiet', '-print_format', 'json', '-show_streams', target])
    except:
      log.error('Unexpected error checking stream info for %s',target)
      return False
    results = json.loads(call_result)
    streams = results['streams']
    log.debug('Streams for %s: %s',target,streams)

    hasHEVC = False
    for stream in streams:
        if 'codec_name' in stream:
            if stream["codec_name"] == "hevc":
                log.debug('Found an hevc encoded stream')
                hasHEVC = True
            else:
                log.debug('codec for stream is %s', stream["codec_name"])
        else:
            log.warning('Stream present in %s with no codec_name value',target)

    return hasHEVC

def processFolder(target = None):
    for root, dirs, files in os.walk(target):
        for name in files:
            # file name w/o extension
            filename = os.path.splitext(name)[0]
            # the extnesion itself (including the '.')
            ext = os.path.splitext(name)[1]
            # The full path to the file (useful for safe deletes and other absolute call
            sourceFullPath = os.path.join(root,name)

            if ext in vid_extensions:

                # Only check files that aren't already marked
                if not filename.endswith(hevcTag):
                    destFullPath = os.path.join(root, filename + hevcTag + ".mkv")

                    statinfo = os.stat(sourceFullPath)

                    # Check if file already uses HEVC codec
                    #   However, since there are other transcode profiles (e.g. fast)
                    #   if the filesize is too large, let's run it anyway

                    if not isHEVC(sourceFullPath) or statinfo.st_size >= FORCE_CONVERSION_MIN_SIZE:

                        log.info('Executing transcode for %s', sourceFullPath)

                        # If the job crashed in the middle of a transcode, delete the partially completed object
                        if os.path.isfile(destFullPath):
                            logging.warning('Destination already exists , this is probably due to a failed prior attempt. Deleting pre-existing destination. source: %s dest: %s', sourceFullPath, destFullPath)
                            safeDelete(destFullPath)

                        # FFMPEG args and reason
                        #   -map 0 -c copy  <- this tells ffmpeg to copy everything over, very important for dual language files w/ subtitles
                        #   -c:v lib265 -preset medium -crf 24 <- use h265 medium preset (medium produces a filesize similar to slow but much faster) quailty rate 24
                        #   -c:a libfdk_aac -b:a 128k <- use libdfk's aac encoder (best quality encoder for mmpeg as of 8/29/16) w/ each channel at 128k bits
                        ff = ffmpy.FFmpeg(
                            inputs={sourceFullPath : None},
                            outputs={destFullPath : '-map 0 -c copy -c:v libx265 -preset medium -crf 24 -c:a libfdk_aac -b:a 128k'})

                        try:
                            # print so we know where we are (it makes me feel better being able to see the ffmpeg command)
                            #  also helpful for debug if ffmpeg crashes out
                            log.debug('FFMPEG command - %s', ff.cmd)
                            # Make the magic happen
                            ff.run()
                            log.info('Transcode complete for %s. Cleaning up', sourceFullPath)
                            log.debug('Deleting the original file')
                            # delete the original file
                            safeDelete(sourceFullPath)
                        except:
                            # FFMPEG choked on something.
                            #  Log the error
                            # Safe Approach
                            if staySafe:
                              log.error('FFMPEG failed for %s, leaving everything in place (including temp files for debug)', sourceFullPath)
                            else:
                              log.error('FFMPEG failed for %s, removing temp files', sourceFullPath)
                              safeDelete(destFullPath)
                    else:
                        logging.info('Video already in HEVC, but not labeled.  Correcting label of r%s.', filename)
                        os.rename(sourceFullPath,destFullPath)
                else:
                    logging.info('Video file already HEVC and labeled. Ignoring %s', filename)


            elif ext in sub_extensions:
                logging.info('Found subtitle file: %s', name)
                if not filename.endswith(hevcTag):
                    logging.warning('sub file missing HEVC tail, renaming %s', name)
                    # rename the subtitle file to math the new name of the transcoded one
                    hevcName = filename + hevcTag + ext
                    os.rename(sourceFullPath, os.path.join(root, hevcName))

            else:
                if deleteUknown:
                    # I don't know what you are, but get out of my library
                    # No, seriously.  The library has some junk files from previous media managers
                    #  e.g. ".cover" files or cover art jpgs.  We don't want those any more.
                    log.info('unknown file type, deleting: %s', sourceFullPath)
                    os.remove(sourceFullPath)
                else:
                    log.info('unknown file type for file: %s', sourceFullPath)
    return


processFolder(target = TARGET_FOLDER)
