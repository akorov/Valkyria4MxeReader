Valkyria4MxeReader is a python script for working with mxe format found in [Valkyria Chronicles 4](https://en.wikipedia.org/wiki/Valkyria_Chronicles_4).
It is similar in goal and function to [ValkyrieEdit](https://github.com/dhavard/ValkyrieEdit) for the first game of the series.

### Capabilities

- Reading the main TOC and associated data according to record classifiers (VlMx_entry_templates.csv in this repo is a basic version)
- Dumping the data into CSV files separated by record type, so they can be sanely perused and edited
- Resolving strings from text_mx.xlb (limited and hacky, but works for that one most important to me file)
- Applying an edited CSV to the in-memory data model and writing it out to the original file, optionally making backups of the original

### Requirements

`Python 3.8+` installed on your system.

### Usage

```
MxeReader.py [-h] [-t TEMPLATE_CSV_PATH] [-d CSV_DIR] [-s SINGLE_CSV] [-x XLB_PATH] [-q] [-l LOG] [-c CONFIG_FILE] [-b] mxe_path {R,T,W,D}

positional arguments:
  mxe_path
  {R,T,W,D}             R: read mode - output MXE file to CSV T: test mode - apply CSV to MXE in-memory only W: write mode - apply CSV to MXE and write out the result. D: dummy mode, will only attempt to read templates, xlb and     
                        MXE into memory

positional arguments:
  mxe_path
  {R,T,W,D}             R: read mode - output MXE file to CSV
                        T: test mode - apply CSV to MXE in-memory only
                        W: write mode - apply CSV to MXE and write out the result.
                        D: dummy mode, will only attempt to read templates, xlb and MXE into memory

options:
  -h, --help            show this help message and exit
  -t TEMPLATE_CSV_PATH, --template-csv-path TEMPLATE_CSV_PATH
                        Path to a CSV file containing record templates.
  -d CSV_DIR, --csv-dir CSV_DIR
                        Path to directory for CSV files. In this directory:
                          - Read mode will save CSV output
                          - Test and Write modes will look for files to apply to MXE
                        This will only be applied if -s is not specified
  -s SINGLE_CSV, --single-csv SINGLE_CSV
                        Path to a single CSV file. Test and Write modes will apply this one file to MXE.
  -x XLB_PATH, --xlb-path XLB_PATH
                        Path to xlb file with text data to resolve MXE text IDs into human-readable stuff, like character and weapon names. Only 'text_mx.xlb' is currently supported (with horrible hacks).
  -q, --quiet           Suppress debug logging write MXE mode
  -l LOG, --log LOG     Path to a debug log file generated when writing MXE.
  -c CONFIG_FILE, --config-file CONFIG_FILE
                        Path to configuration file. If omitted, hardcoded defaults are used.
  -b, --backup-mxe      Back up MXE file when writing it out. Only used with W mode.
```

### Examples:

After extracting .mxe and .xlb, put them in the same place as VlMx_entry_templates.csv. For examples below it will be `F:\\test\\`

Assuming you have python installed and associated properly:
1) read records with default parameters and output CSVs under F:\\test:\\game_info - original\\ *.csv

`.\MxeReader.py "F:\\test\\game_info.mxe" R`

2) read records with manually specifying a different output location

`.\MxeReader.py "F:\\test\\game_info.mxe" R -d "F:\\some_other_dir"`

3) read records with manually specifying a different template file

`.\MxeReader.py "F:\\test\\game_info.mxe" R -t "F:\\some\\other\\place\\my_mxe_templates.csv"`

4) read records with a different config file. Maybe you want to force hex output for all data.

`.\MxeReader.py "F:\\test\\game_info.mxe" R -c "F:\\path\\to\\new\\config.json"`

5) try applying your changes in csv files to mxe to look for crahses (no writing, no risk of breaking stuff)

`.\MxeReader.py "F:\\test\\game_info.mxe" T`

6) write out the mxe with default locations for everything and a backup produced

`.\MxeReader.py "F:\\test\\game_info.mxe" W -b`

7) run a dummy execution which will only try to parse arguments and read MXE into memory

`.\MxeReader.py "F:\\test\\game_info.mxe" D`