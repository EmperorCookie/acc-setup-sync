from pprint import pprint
import argparse
import contextlib
import logging
import os
import shutil
import sys
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

ACC_TRACK_FOLDERS = \
[
    "Barcelona",
    "brands_hatch",
    "Hungaroring",
    "Kyalami",
    "Laguna_Seca",
    "misano",
    "monza",
    "mount_panorama",
    "nurburgring",
    "Paul_Ricard",
    "Silverstone",
    "Spa",
    "Suzuka",
    "Zandvoort",
    "Zolder"
]

# PausingObserver from https://stackoverflow.com/a/26853551/1042651
class PausingObserver(Observer):
    def dispatch_events(self, *args, **kwargs):
        if not getattr(self, '_is_paused', False):
            super(PausingObserver, self).dispatch_events(*args, **kwargs)

    def pause(self):
        logging.debug("Pausing")
        self._is_paused = True

    def resume(self):
        logging.debug("Resuming")
        time.sleep(self.timeout)  # allow interim events to be queued
        self.event_queue.queue.clear()
        self._is_paused = False

    @contextlib.contextmanager
    def ignore_events(self):
        self.pause()
        yield
        self.resume()

class EventHandler(FileSystemEventHandler):
    def __init__(self, observer):
        self._observer = observer

    def on_modified(self, event):
        
        # Pause all watching since we will be making a lot of changes
        with self._observer.ignore_events():
            
            # Print event information for assistance
            logging.debug("Received event")
            logging.debug(", ".join([f"{a}: {getattr(event, a)}" for a in event.__dir__() if a[0] != "_" and a != "key"]))

            # Get track and car names
            if event.is_directory:
                trackDir = event.src_path
                setupName = None
            else:
                trackDir = os.path.dirname(event.src_path)
                setupPath = event.src_path
                setupName = os.path.basename(setupPath)
            carDir, trackName = os.path.split(trackDir)
            _, carName = os.path.split(carDir)
            if carName == "Setups":
                logging.debug(f"Contents of car folder was modified, ignoring")
                return
            logging.info(f"Change -> track: {trackName}, car: {carName}" + (" (folder)" if event.is_directory else f", setup: {setupName}"))

            # Make sure all directories exist
            create_track_dirs(carDir)

            # A new file has been added
            if event.is_directory:

                # Get files in modified directory
                setups = list_dir(trackDir, files = True)

                # Copy non-existant files to every other track
                logging.debug(f"Synchronizing all setups from track {trackName}")
                for track in ACC_TRACK_FOLDERS:

                    # Skip source track
                    if track == trackName:
                        logging.debug(f"Skipping source track {trackName}")
                        continue
                    
                    # Copy setups
                    for setup in setups:
                        targetPath = os.path.join(carDir, track, setup)
                        if not os.path.isfile(targetPath):
                            logging.info(f"Copying {setup} from {trackName} to {track}")
                            shutil.copy(setupPath, targetPath)
                        else:
                            logging.debug(f"Skipping {track}/{setup}, already exists")
                        
                    # Remove deleted setups
                    targetPath = os.path.join(carDir, track)
                    trackSetups = list_dir(targetPath, files = True)
                    for setup in trackSetups:
                        if setup not in setups:
                            logging.info(f"Removing deleted setup {setup} from {track}")
                            os.remove(os.path.join(targetPath, setup))

            # An existing file has been modified
            else:
                
                # Copy changes to every other track
                for track in ACC_TRACK_FOLDERS:
                    if track == trackName:
                        logging.debug(f"Skipping source track {trackName}")
                        continue
                    logging.info(f"Copying {setupName} from {trackName} to {track}")
                    targetPath = os.path.join(carDir, track, setupName)
                    shutil.copyfile(setupPath, targetPath)

def list_dir(path, files = False, dirs = False):
    return [f for f in os.listdir(path) if files and os.path.isfile(os.path.join(path, f)) or dirs and os.path.isdir(os.path.join(path, f))]

def create_track_dirs(carDir):
    _, car = os.path.split(carDir)
    logging.debug(f"Making sure all directories exist for car {car}")
    for track in ACC_TRACK_FOLDERS:
        targetPath = os.path.join(carDir, track)
        if not os.path.isdir(targetPath):
            logging.info(f"Creating missing directory {car}/{track}")
            os.mkdir(targetPath)
        else:
            logging.debug(f"Directory already exists for track {track}")

def init(setupsPath):
    """
    Goes in each car and track folder and copies setups to every other track.

    Args:
        setupsPath (str): The root setups folder.
    """
    cars = list_dir(setupsPath, dirs = True)
    for car in cars:
        carPath = os.path.join(setupsPath, car)

        # Make sure all track directories exist
        create_track_dirs(carPath)

        # Find and rename all existing setups
        setupPaths = []
        for track in ACC_TRACK_FOLDERS:
            trackPath = os.path.join(carPath, track)
            setups = list_dir(trackPath, files = True)
            for setup in setups:
                
                # Add track name to setup
                newName = f"{track}-{setup}"
                sourcePath = os.path.join(trackPath, setup)
                targetPath = os.path.join(trackPath, newName)
                logging.info(f"Renaming setup {track}/{setup} to {track}/{newName}")
                shutil.move(sourcePath, targetPath)
                setupPaths.append(targetPath)

        # Copy every setup
        for setupPath in setupPaths:

            # To every track
            for track in ACC_TRACK_FOLDERS:
                trackPath = os.path.join(carPath, track)

                setupTrackPath, setupName = os.path.split(setupPath)
                _, setupTrack = os.path.split(setupTrackPath)
                targetPath = os.path.join(trackPath, os.path.basename(setupPath))

                # Do not copy file to itself
                if setupPath == targetPath:
                    logging.debug(f"Skipping {track}/{setupName}")
                    continue

                # Copy setup
                logging.info(f"Copying setup {setupName} from track {setupTrack} to track {track}")
                shutil.copyfile(setupPath, targetPath)

def parse_args(*args):
    
    # Log levels
    logLevels = \
    {
        "NOTSET": logging.NOTSET,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    # Argument parser
    parser = argparse.ArgumentParser(
        description = "Watches the ACC setups folder for changes and reproduces those changes across all tracks."
    )

    # Add arguments
    parser.add_argument(
        "-v", "--verbosity",
        help = "Sets the verbosity.",
        choices = logLevels.keys(),
        type = str,
        default = "INFO"
    )
    parser.add_argument(
        "-i", "--init",
        help = "Initializes setups by going to each car and track folder and copying existing setups to every other track, adding the track name in front to avoid name collisions.",
        action = "store_true"
    )
    parser.add_argument(
        "setupsPath",
        help = r"Path to the setups folder (Usually 'C:\Users\<user>\Documents\Assetto Corsa Competizione\Setups').",
        type = str
    )

    # Parse arguments
    args = parser.parse_args()
    args.verbosity = logLevels[args.verbosity]
    args.setupsPath = os.path.abspath(args.setupsPath)
    return args

def main(args):

    # Setup logging
    logging.basicConfig(format = "[%(levelname)s] %(message)s", level = args.verbosity)

    if args.init:
        logging.info("Initializing setups folder to avoid losing existing setups.")
        init(args.setupsPath)
        logging.info("Completed.")
        return 0

    # Create event handler and observe the setups path
    observer = PausingObserver()
    eventHandler = EventHandler(observer)
    observer.schedule(eventHandler, path = args.setupsPath, recursive = True)
    observer.setDaemon(True)
    logging.debug("Starting observer thread")
    observer.start()

    # Allow the script to be stopped via sigint
    logging.info("Stop with ctrl+c")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.debug("Received keyboard interrupt, stopping observer thread")
        observer.stop()
    logging.debug("Waiting for observer thread to end")
    observer.join()

    # Success
    return 0

if __name__ == "__main__":
    args = parse_args(*sys.argv[1:])
    sys.exit(main(args))
