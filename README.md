# acc-setup-sync
Synchronizes Assetto Corsa Competizione setups to be available across all tracks.

## Usage
1. Make a backup of your setups, they will be renamed and copied all over the place
1. Run `pip install -r requirements.txt` to install the required modules
1. Run `python accSetupSync.py -i <pathToYourSetups>` to copy your setups to all tracks, while also making their names unique
    - Do not run this more than once, it will exponentially create new copies of existing setups!
1. Run `python accSetupSync.py <pathToYourSetups>` to start watching the setups folders for changes
1. Use ctrl+c to terminate
