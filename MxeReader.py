import os
import csv
import struct
import codecs
import sys
import shutil
import datetime
import argparse
from argparse import RawTextHelpFormatter
import json

""" ---------------------------------------------------"""
"""                        Settings                    """
""" ---------------------------------------------------"""
# file with record templates
template_path=""
# path to mxe
mxe_path = ""
# directory with/for CSVs
csv_directory = ""
# CSV path for single apply option
csv_path = ""
# path to xlb file with text strings
xlb_path = ""
# debug log used when writing out MXE
debug_log = ""

# MXE SETTINGS - can be altered via -c option
MXE_SETTINGS = {
    # this is added to every 0-based address
    "MXE_ADDRESS_OFFSET": 0x40,
    # where the count of main entry tables is stored
    "MAIN_TABLE_COUNT_ADDR": 0xC8,
    # where the start address of main table is stored
    "MAIN_TABLE_STARTADDR_ADDR": 0xE0,

    # total length of main table's table of contents entry
    "TOC_ENTRY_SIZE": 32,
    # < for little endian, > for big endian
    "TOC_ENDIANNESS": "<",
    # offsets for various TOC fields in toc entry (all 4-byte integers)
    "TOC_FIELD_ID": 0,
    "TOC_FIELD_TYPE": 4,
    "TOC_FIELD_TYPENAME_ADDR": 8,
    "TOC_FIELD_RECORD_ADDR": 16,
    # follow pointers to get underlying values
    "RESOLVE_CLASSIC_POINTERS": True,
    "RESOLVE_XLB_POINTERS": True,
    "RESOLVE_XLB_STRINGS": True
}

# output to csv modifiers - can be altered via -c option
OUTPUT_MODIFIERS = {
    "FORCE_HEX_OUTPUT": False,               # force output everything as hex, this overrules everything else
    "FORCE_RAW_CLASSIC_POINTERS": False,     # do not output resolved values of classic pointers, output pointers themselves instead
    "FORCE_RAW_XLB_POINTERS": False,         # do not output resolved values of xlb pointers, output pointers themselves instead
    "FORCE_XLB_IDS": False                   # do not output resolved xlb strings, output xlb string IDs instead
}

""" ---------------------------------------------------"""
"""              Data types, converters                """
""" ---------------------------------------------------"""

"""
    Datatype->length of record in bytes
    These are used in templates to describe record structure.
"""
DataTypes = {
    "<i": 4,  # int
    "<i2": 2, # short int
    "<f": 4,  # float
    "<h": 4,  # hex-as-string sequence (e.g. 0x12-34-ab-cd)

    ">i": 4,  # big-endian int
    ">i2": 2, # big-endian short int
    ">f": 4,  # big-endian float
    ">h": 4,  # big-endian hex-as-string sequence (e.g. 0x12-34-ab-cd)

    "i1": 1, # char (1-byte integer)

    "<ip": 4, # direct id from xlb text container file (external/player-visible text is sometimes this)
    "<pi": 4, # address of string with id from xlb text container file (external/player-visible text is usually this)
    "<p": 4,   # address of string with text in mxe (usually internal text in VC4)

    ">ip": 4, # big-endian direct id from xlb text container file
    ">pi": 4, # big-endian address of string with id from xlb text container file 
    ">p": 4   # big-endian address of string with text in mxe
}

"""
    Converter wrapper functions from bytes datatype
"""
def bytesAsLEInt(buf):
    return struct.unpack_from("<i", buf, 0)[0]

def bytesAsLEShort(buf):
    return struct.unpack_from("<h", buf, 0)[0]

def bytesAsChar(buf):
    return struct.unpack_from("<b", buf, 0)[0]

def bytesAsBEInt(buf):
    return struct.unpack_from(">i", buf, 0)[0]

def bytesAsBEShort(buf):
    return struct.unpack_from(">h", buf, 0)[0]

# Strictly speaking, rounding like this is bad and data loss but it's only barely ever relevant if doing unit placement.... maybe...
# Most values in float have no actual partial value. There are also occasionally very small (<0.001) values in places 
# where game engine surely uses 0 (like anti-accuracy field in weapon records). 
# For practical purposes, it's perfectly fine to just return round to 2 digits, although ability to rebuild original MXE 1-to-1 is lost this way
def bytesAsLEFloat(buf):
    # res = struct.unpack_from("<f", buf, 0)[0]
    # if res < 0.01:
    #     return res
    # else:
    #     return round(res,2)
    return round(struct.unpack_from("<f", buf, 0)[0],2)

# see comment above
def bytesAsBEFloat(buf):
    # res = struct.unpack_from(">f", buf, 0)[0]
    # if res < 0.01:
    #     return res
    # else:
    #     return round(res,2)
    return round(struct.unpack_from(">f", buf, 0)[0],2)

def bytesAsLEHex(buf):
    s = '0x'
    for byte in reversed(buf):
        s += hex(byte)[2:].zfill(2).upper() + "-"
    return s[:-1]

def bytesAsBEHex(buf):
    s = '0x'
    for byte in buf:
        s += hex(byte)[2:].zfill(2).upper() + "-"
    return s[:-1]  

def bytesAsLEAddress(buf):
    return bytesAsLEInt(buf)

def bytesAsBEAddress(buf):
    return bytesAsBEInt(buf)

def bytesAsString(buf, enc: str = 'shift_jisx0213'):
    return buf.decode(enc).rstrip('\x00')

"""
    Converter wrapper functions to bytes
"""
def leIntAsBytes(obj):
    return struct.pack("<i", int(obj))

def leShortAsBytes(obj):
    return struct.pack("<h", int(obj))

def charAsBytes(obj):
    return struct.pack("<b", int(obj))

def beIntAsBytes(obj):
    return struct.pack(">i", int(obj))

def beShortAsBytes(obj):
    return struct.pack(">h", int(obj))

def leFloatAsBytes(obj):
    return struct.pack("<f", float(obj))

def beFloatAsBytes(obj):
    return struct.pack(">f", float(obj))

def leHexAsBytes(obj):
    b = str(obj).replace('-', '').replace('0x', '')
    c = struct.unpack("<i", codecs.decode(b, "hex"))[0]
    return struct.pack("<i", c)

def beHexAsBytes(obj):
    b = str(obj).replace('-', '').replace('0x', '')
    c = struct.unpack(">i", codecs.decode(b, "hex"))[0]
    return struct.pack(">i", c)

def leAddressAsBytes(obj):
    return leIntAsBytes(obj)

def beAddressAsBytes(obj):
    return beIntAsBytes(obj)

def stringAsBytes(obj: str, enc: str = 'shift_jisx0213'):
    return obj.encode(enc)

"""
    map dataTypes->converter functions
"""
ConvertFunctions = {
    "<i": bytesAsLEInt,
    "<i2": bytesAsLEShort,
    "<f": bytesAsLEFloat,
    "<h": bytesAsLEHex,
    
    ">i": bytesAsBEInt,
    ">i2": bytesAsBEShort,
    ">f": bytesAsBEFloat,
    ">h": bytesAsBEHex,

    "i1": bytesAsChar,

    "<ip": bytesAsLEAddress,
    "<pi": bytesAsLEAddress,
    "<p": bytesAsLEAddress,

    ">ip": bytesAsBEAddress,
    ">pi": bytesAsBEAddress,
    ">p": bytesAsBEAddress,

    "s": bytesAsString
}

ConvertBackFunctions = {
    "<i": leIntAsBytes,
    "<i2": leShortAsBytes,
    "<f": leFloatAsBytes,
    "<h": leHexAsBytes,
    
    ">i": beIntAsBytes,
    ">i2": beShortAsBytes,
    ">f": beFloatAsBytes,
    ">h": beHexAsBytes,

    "i1": charAsBytes,

    "<ip": leAddressAsBytes,
    "<pi": leAddressAsBytes,
    "<p": leAddressAsBytes,

    ">ip": beAddressAsBytes,
    ">pi": beAddressAsBytes,
    ">p": beAddressAsBytes,

    "s": stringAsBytes
}

"""
    Converter wrapper that autoselects based on desired datatype from ConvertFunctions
    There's no way to pass a different string encoding because there's no point, shift_jisx0213 works for all files I tried
"""
def bytesToText(buf, dataType: str):
    func = ConvertFunctions.get(dataType)
    if func != None:
        return func(buf)
    else:
        return None

def objToBytes(obj, dataType: str)->bytes:
    func = ConvertBackFunctions.get(dataType)
    if func != None:
        return func(obj)
    else:
        return None

""" ---------------------------------------------------"""
"""                  Support formats                   """
""" ---------------------------------------------------"""
def readTemplates(path:str) -> list:
    """
        Reads mxe entry templates from file
        Returned template structure: [ [ NAME, [(FIELD DATA TYPE, FIELD NAME)] ] ]
    """ 
    templates = []
    with open(path, newline = '')  as template_csv:
        reader = csv.reader(template_csv, delimiter=',', quotechar='"')
        for row in reader:
            templates.append( [ row[0], [ tuple(x.split(':',1)) if ":" in x else (x, '') for x in row[1:]]] )
    return templates

def followAddress(raw_address: int, offset: int = MXE_SETTINGS.get("MXE_ADDRESS_OFFSET")) -> int:
    """ Follow mxe address arithmetic.
        This should be used to traverse addresses so that lists store real data as-is.
    """
    return raw_address+offset

def readZeroDelBytes(file, startpos: int, backseek: int) -> bytearray:
    """
        Returns: bytearray object
        Read 0-delimeted byte sequence from <startpos> and return to <backseek>. If backseek is not required, use negative argument, e.g. -1
        In MXE such sequences are usually detached from data, so we need to go back.
    """
    barr = bytearray()
    file.seek(startpos)
    while True:
        c = file.read(1)
        if c is not None and c != b'\x00':
            barr += bytearray(c)
        else:
            break
    if (backseek > 0):
        file.seek(backseek)
    return barr

def readStr(file, startpos: int, backseek: int, encoding: str="shift_jisx0213"):
    """
        Returns: decoded string
        Read 0-delimeted string from <startpos> and return to <backseek>. If backseek is not required, use negative argument, e.g. -1
        In MXE most strings are detached from data.
        shift_jisx0213 is the default encoding for VlMx<something> entries, which are internal/for devs.
        Most in-game text is encoded outside of MXE files in VC4.
    """
    bytearr = readZeroDelBytes(file, startpos, backseek)
    return codecs.decode(bytearr,encoding)

def readXLB(file_path: str, encoding:str="shift_jisx0213"):
    """
        Hopefully read XLB text file. Format is a bit magical to me, so there are lv.80 manual parsing-based crutches involved.
        General rules seem to be:
            1) next id row = orders of 16 for sub-ids. So if next_id - prev_id = 16, next goes into next row, 32 -> skip 1, 48 = skip 2 etc.
            2) entering new section, including 1st, "costs" extra 3 rows worth of IDs (or 48)
            3) there may be empty sections
        Jumping between sections is messy and sometimes doesn't match rules above. Some sections match id count to string count 1-to-1, 
        so they should obviously start at 0th row but that doesn't always match new line calculation rules above.
        Either the format isn't standalone (unlikely) or I just plain messed up my understanding of it (most likely). Either way, it sorta works for text_mx.xlb which is all I need atm :)
        
        output format:
        [
            [
                [recordSize, recordCount, description byte count, description bytes],
                [
                    [id, text bytes],
                    ...
                ]
            ],
            ...
        ]
    """
    print("Reading XLB file: " + file_path)
    f=open(file_path,"rb")
    
    data = []
    f.seek(0x4)
    typeCount = bytesAsLEInt(f.read(4))
    f.seek(0x10)
    for _ in range(0,typeCount):
        # read header + entries
        recordSize = bytesAsLEInt(f.read(4))
        recordCount = bytesAsLEInt(f.read(4))
        descrLen = bytesAsLEInt(f.read(4))
        descr = codecs.decode(f.read(descrLen),encoding)
        rec_header = [ recordSize, recordCount, descrLen, descr]
        # read records for this header
        records = []
        for _ in range(0, recordCount):
            id = bytesAsLEInt(f.read(4))
            records.append( [ id, '' ] )
            f.seek(f.tell()+(recordSize-4))

        # add everything to data
        data.append( [ rec_header, records] )

    # read actual data
    chnkhead = bytesAsString(f.read(4))
    if chnkhead != "CHNK":
        print("Error reading XLB, expected CHNK after TOC at position " + str(f.tell()-4))
        return data
    recordCount = bytesAsLEInt(f.read(4))

    currHeader = 0 # header in data we currently write to
    currRec = 0    # record in header we currently write to

    #read first record by hand
    rec_id2 = bytesAsLEInt(f.read(4))
    rec_size = bytesAsLEInt(f.read(4))
    rec_bytes = f.read(rec_size)
    # remember previous id
    prev_id2 = rec_id2
    # calculate offset from 48
    currRec += (rec_id2-48)//16
    # write data
    data[currHeader][1][currRec][1] = rec_bytes
    # already read record count
    i = 1

    # read other records
    while(i < recordCount):
        # read new record
        rec_id2 = bytesAsLEInt(f.read(4))
        rec_size = bytesAsLEInt(f.read(4))
        rec_bytes = f.read(rec_size)
        # calculate difference between two records
        add = (rec_id2 - prev_id2)//16
       
        if(currRec+add < data[currHeader][0][1]):
            # within the same type, just add record
            currRec = currRec+add
        else:
            # we reached the end of current type, calculate carryover
            empty_old = data[currHeader][0][1] - 1 - currRec
            currHeader += 1
            currRec = add-empty_old-3
                        
            #print("new header=" + str(currHeader) + "| currRec=" + str(currRec))
            #print("short header test:" + str(currRec) + "?>" + str(data[currHeader][0][1]))
            
            #crutches for places where format is apparently not respected
            if (rec_id2 == 108184 and prev_id2 == 108120):
                currRec = 0
                #print("StageInfo->ResultInfo transition fix")
            if (rec_id2 == 157496 and prev_id2 == 157368):
                currRec = 0
                #print("WeaponRDInfo->GenericNames transition fix")            
            if (rec_id2 == 160312 and prev_id2 == 160248):
                currRec = 0
                #print("JobInfo->VehicleDev transition fix") 
            if (rec_id2 == 177416 and prev_id2 == 175880):
                currRec = 1
                #print("VehicleAffiliation->Ranks transition fix")
            if (rec_id2 == 174456 and prev_id2 == 172856):
                currRec = 0
                #print("CharacterEach->VehicleEach transition fix")
             
            # re-check for [normally] small empty type inbetween two
            while(currRec > data[currHeader][0][1]):
                currRec = currRec-(data[currHeader][0][1]-1)-3
                currHeader += 1
                #print("new header/short skip=" + str(currHeader) + "| currRec=" + str(currRec))


        #print("currHeader=" + str(currHeader) + " | currRec=" + str(currRec))
        data[currHeader][1][currRec][1] = rec_bytes
        
        prev_id2 = rec_id2
        i = i+1
    #print("Done")
    return data

def findByIDInXLB(data: list, id: int) -> bytes:
    """
        Return a string by xlb id or None if not found. See readXLB for expected data structure.
        I am not sorry for the old school loops.
    """
    i = 0
    while(i < len(data)):
        j = 0
        while(j < len(data[i][1])):
            if(int(data[i][1][j][0]) == id):
                return data[i][1][j][1]
            j += 1
        i += 1
    return None


""" ---------------------------------------------------"""
"""                  MXE functions                    """
""" ---------------------------------------------------"""

"""
    These functions read/write MXE file's main TOC and associated contents using a list of provided pre-made record templates. 
    Does not read extra sections like PCRF, or extra possible tables that may be referenced at the start of the file in various MXEs.
    For editing existing records, a CSV file can be applied to in-memory mxe model. Adding new records is not supported.
    Format:
    main_table = [
        [
            toc_field_id: int, 
            toc_field_type: int, 
            [ 
                toc_type_string_addr: int, 
                toc_type_string: str 
            ],
            record_address,
            [ record data according to template ]
        ],
        ...
    ]
"""

def readMXEFile(mxe_path: str, templates: list, mxe_settings: dict = MXE_SETTINGS) -> list:
    """
        Step 1: Read main TOC
    """
    print("Reading main mxe TOC... ", end='')
    f=open(mxe_path,"rb")
    f.seek(mxe_settings.get("MAIN_TABLE_COUNT_ADDR"))
    raw = f.read(4)
    entry_count = struct.unpack_from("<i", raw)[0]
    
    f.seek(mxe_settings.get("MAIN_TABLE_STARTADDR_ADDR"))
    raw = f.read(4)
    entry_start = struct.unpack_from("<i", raw)[0]
    f.seek(followAddress(entry_start))
    main_table = []
    for _ in range(0, entry_count):
        buf = f.read(mxe_settings.get("TOC_ENTRY_SIZE"))
        a1 = struct.unpack_from(mxe_settings.get("TOC_ENDIANNESS")+"i", buf, mxe_settings.get("TOC_FIELD_TYPENAME_ADDR"))[0]
        main_table.append( [
            struct.unpack_from(mxe_settings.get("TOC_ENDIANNESS")+"i", buf, mxe_settings.get("TOC_FIELD_ID"))[0], 
            struct.unpack_from(mxe_settings.get("TOC_ENDIANNESS")+"i", buf, mxe_settings.get("TOC_FIELD_TYPE"))[0], 
            [
                a1,
                readStr(f, followAddress(a1), f.tell())
            ],
            struct.unpack_from(mxe_settings.get("TOC_ENDIANNESS")+"i", buf, mxe_settings.get("TOC_FIELD_RECORD_ADDR"))[0],
            []
            ] )
    print("Done, total entry count is: " + str(entry_count))

    """
        Step 2: Read data entries defined by TOC from mxe
    """
    print("Reading data entries... ", end='')
    n = 0
    for entry in main_table:
        try:
            # find template
            template = [ s for s in templates if s[0] == str(entry[2][1].split(':')[0])][0]
            # go to starting address
            f.seek(followAddress(entry[3]))
            for dt,name in template[1]:
                done = False
                if DataTypes.get(dt) != None:
                    if (dt == "<p" or dt == ">p") and mxe_settings.get("RESOLVE_CLASSIC_POINTERS"):
                        raw_addr = f.read(DataTypes.get(dt))
                        int_addr = bytesAsLEInt(raw_addr) if dt == "<p" else bytesAsBEInt(raw_addr)
                        val = readStr(f, followAddress(int_addr), f.tell())
                        entry[4].append([raw_addr, val])
                        done = True
                    if (dt == "<pi" or dt == ">pi") and mxe_settings.get("RESOLVE_XLB_POINTERS"):
                        raw_addr = f.read(DataTypes.get(dt))
                        int_addr = bytesAsLEInt(raw_addr) if dt == "<pi" else bytesAsBEInt(raw_addr)
                        val = bytes(readZeroDelBytes(f, followAddress(int_addr), f.tell()))
                        entry[4].append([raw_addr, val])
                        done = True                       
                    if not done:
                        entry[4].append(f.read(DataTypes.get(dt)))
                else:
                    print("Illegal template definition encountered and will be skipped: Field '" + dt + ":" + name + "' in template " + template[0])

        except IndexError:
            print("Template not found for: '"+ entry[2][1].split(':')[0] + "', entry "+ str(n) + " will be skipped")
        n += 1

    print("Done, total entries read: " + str(n))
    f.close()
    return main_table

def writeMXEFile(mxe_path: str, main_table: list, templates: list, mxe_settings: dict = MXE_SETTINGS, backup: bool = True, debug:bool = False, debug_log: str = ""):
    if(backup):
        print("Making a backup... ")
        try:
            shutil.copyfile(mxe_path, mxe_path + "_" + datetime.datetime.now().strftime("%Y-%m-%dT%H_%M_%S.bak"))
        except:
            print("Error:", sys.exc_info()[0])
            return
        print("Done")
    
    print("Writing out mxe...")
    
    if debug and debug_log != "" and debug_log != None:
        mylog = open(debug_log, "w", encoding='utf-8')
    else:
        mylog = sys.stdout

    with open(mxe_path, "r+b") as f:
        n = 0
        for entry in main_table:
            try:
                # find template
                template = [ s for s in templates if s[0] == str(entry[2][1].split(':')[0])][0]
                if debug:
                    mylog.write(str(template) + "\n")

                # go to start
                f.seek(followAddress(int(entry[3])))
                if debug:
                    mylog.write("Seek to: " + str(followAddress(int(entry[3]))) + "\n")
                i = 0
                for dt,name in template[1]:
                    if debug:
                        mylog.write("n=" + str(n) + " | i=" + str(i) + "  |  dt=" + str(DataTypes.get(dt)) + "\n")
                    if DataTypes.get(dt) != None:
                        # address is already stored raw as it was read
                        done = False
                        if (dt == "<p" or dt == ">p") and mxe_settings.get("RESOLVE_CLASSIC_POINTERS"):
                            f.write(bytearray(entry[4][i][0]))
                            if debug:
                                mylog.write("if <p Wrote:" + str(entry[4][i][0]) + "\n")
                            done = True
                        if (dt == "<pi" or dt == ">pi") and mxe_settings.get("RESOLVE_XLB_POINTERS"):
                            f.write(bytearray(entry[4][i][0]))
                            if debug:
                                mylog.write("if <pi-strings Wrote:" + str(entry[4][i][0]) + "\n")
                            done = True
                        # if (dt == "<ip" or dt == ">ip"):
                        #     f.write(bytearray(entry[4][i][0]))
                        #     mylog.write("if <ip Wrote:" + str(entry[4][i]) + "\n")
                        #     done = True
                        if not done:
                            f.write(bytearray(entry[4][i]))
                            if debug:
                                mylog.write("default Wrote:" + str(entry[4][i]) + "\n")
                    else:
                        print("Illegal template definition encountered and will be skipped: Field '" + dt + ":" + name + "' in template " + template[0])
                        if debug:
                            mylog.write("Illegal template definition encountered and will be skipped: Field '" + dt + ":" + name + "' in template " + str(template[0]))
                    i += 1
            except IndexError:
                print("Template not found for: '"+ entry[2][1].split(':')[0] + "', entry "+ str(n) + " will be skipped")
                if debug:
                    mylog.write("Template not found for: '"+ entry[2][1].split(':')[0] + "', entry "+ str(n) + " will be skipped")
            n += 1

        print("Done. Wrote " + str(n) + " entries.")
    if debug:
        mylog.close()
    return

def writeMXEtoCSV(main_table: list, templates:list, out_csv_directory: str, xlb_path: str, mxe_settings: dict = MXE_SETTINGS, output_modifiers: dict = OUTPUT_MODIFIERS): 
    # check/create directory
    if not os.path.exists(out_csv_directory):
        os.makedirs(out_csv_directory)

    # read xlb for name resolution if needed
    if mxe_settings.get("RESOLVE_XLB_STRINGS"):
        xlb_list = readXLB(xlb_path)

    # templates actually found in data
    uniq_templates = { str(entry[2][1].split(':')[0]) for entry in main_table }

    for templ_name in uniq_templates:
        out_csv_file = os.path.join(out_csv_directory, templ_name + ".csv")
        with open(out_csv_file, 'w', newline='', encoding='shift-jisx0213') as out_csv:
            writer = csv.writer(out_csv, delimiter=',', quotechar='"')
            
            # write template to 1st row
            template = [ s for s in templates if s[0] == templ_name][0]
            row = [ 'RecordId', 'InternalName' ]
            for t in template[1]:
                if (t[1] == ''):
                    row.append(t[0])
                else:
                    row.append(t[0]+":"+t[1])
            writer.writerow(row)
            # write data entries
            for entry in main_table:
                if str(entry[2][1].split(':')[0]) == templ_name:
                    i = 0
                    row = [ entry[0], entry[2][1] ]
                    for data in entry[4]:
                        done = False
                        if output_modifiers.get("FORCE_HEX_OUTPUT"):
                            row.append(bytesAsBEHex(data))
                        else:
                            # classic pointer
                            if template[1][i][0] == "<p" or template[1][i][0] == ">p":
                                if output_modifiers.get("FORCE_RAW_CLASSIC_POINTERS"):
                                    row.append(bytesToText(data, template[1][i][0]))
                                else:
                                    if mxe_settings.get("RESOLVE_CLASSIC_POINTERS") == False:
                                        row.append(bytesToText(data, template[1][i][0]))
                                    else:
                                        row.append(data[1])
                                done = True
                            # xlb pointer
                            if template[1][i][0] == "<pi" or template[1][i][0] == ">pi":    
                                if output_modifiers.get("FORCE_RAW_XLB_POINTERS"):
                                    if mxe_settings.get("RESOLVE_XLB_POINTERS") == False:
                                        row.append(bytesToText(data, template[1][i][0]))
                                    else:
                                        row.append(bytesToText(data[0], template[1][i][0]))
                                else:
                                    if mxe_settings.get("RESOLVE_XLB_POINTERS") == False:
                                        row.append(bytesToText(data, template[1][i][0]))
                                    else:
                                        if mxe_settings.get("RESOLVE_XLB_STRINGS"):
                                            if output_modifiers.get("FORCE_XLB_IDS"):
                                                row.append(bytesToText(data, template[1][i][0]))
                                            else:
                                                if data[1] != b'':
                                                    try:
                                                        a = int( data[1] )
                                                        res = findByIDInXLB(xlb_list, a)
                                                        if res != '' and res != None:
                                                            row.append(bytesToText(res, "s").replace("\n", "\\LF"))
                                                        else:
                                                            row.append("")
                                                    except ValueError:
                                                        row.append(bytesToText(data[1], "s").replace("\n", "\\LF"))
                                                else:
                                                    row.append("")
                                        else:
                                            row.append(bytesToText(data[1], "s").replace("\n", "\\LF"))
                                done = True
                            # non-pointer data
                            if not done:
                                row.append(bytesToText(data, template[1][i][0]))
                        i = i+1
                    writer.writerow(row)

def applyCSVtoMXE(main_table: list, templates:list, csv_path: str)-> list:
    print("Processing csv file: " + csv_path)
    with open(csv_path, newline='', encoding='shift-jisx0213') as in_csv:
        reader = csv.reader(in_csv, delimiter=',', quotechar='"')
        header_row = []
        template = []

        for row in reader:
            if reader.line_num == 1:
                #process header line
                if row[0] != "RecordId" or row[1] != "InternalName":
                    print("Error: expected first columns: 'RecordId,InternalName', found: '" + row[0] + "," + row[1] +"'")
                    return
                header_row = [ tuple(x.split(':',1)) if ":" in x else (x, '') for x in row[2:]]
            else:
                # find template
                if reader.line_num == 2:
                    template = [ s for s in templates if s[0] == str(row[1].split(':')[0])][0]
                #find record
                try:
                    entry = main_table[int(row[0])][4]
                except IndexError:
                    print("CSV idx=" + str(row[0]) + ": not found in mxe main table and will be skipped")
                i = 0
                for (dt, _) in template[1]:
                    try:
                        if header_row[i][0] != dt:
                            print("CSV idx=" + str(row[0]) + ": skipping mismatched datatype - template=" + dt + "; csv header=" + header_row[i][0])
                        else:
                            if dt == "<p" or dt == ">p" or dt == "<pi" or dt == ">pi" or dt == "<ip" or dt == ">ip":
                                print("CSV idx=" + str(row[0]) + ", col=" + str(i) + ": pointer datatype, skipping")
                            else:
                                b = objToBytes(row[2+i], dt)
                                if entry[i] != b:
                                    print("CSV idx=" + str(row[0]) + ", col=" + str(i) + ": changing value '" + str(entry[i]) + "' -> '" + str(b) + "'")
                                    entry[i] = b
                    except IndexError:
                        print("CSV idx=" + str(row[0]) + ": template " + template[0] + " has more fields than real data, error at column " + str(i))
                    i += 1
    return main_table

def applyCSVDIRtoMXE(main_table: list, templates:list, csv_dir: str):
    print("Processing location: " + csv_dir)
    file_names = [fn for fn in os.listdir(csv_dir) if fn.endswith(".csv")]
    print("Found csv files: " + str(len(file_names)))
    for csv_path in file_names:
        applyCSVtoMXE(main_table, templates, os.path.join(csv_dir, csv_path))





"""---------------------------------------------------"""
"""                         MAIN                      """
"""---------------------------------------------------"""


parser = argparse.ArgumentParser(description="Script for reading and editing main MXE table for Valkyria Chronicles 4.", formatter_class=RawTextHelpFormatter)
parser.add_argument("mxe_path", type=str)
parser.add_argument("mode", choices=[ 'R', 'T', 'W', 'D' ], help="R: read mode - output MXE file to CSV\r\nT: test mode - apply CSV to MXE in-memory only\r\nW: write mode - apply CSV to MXE and write out the result.\r\nD: dummy mode, will only attempt to read templates, xlb and MXE into memory")
parser.add_argument("-t", "--template-csv-path", type=str, help="Path to a CSV file containing record templates.")
parser.add_argument("-d", "--csv-dir", type=str, help="Path to directory for CSV files. In this directory:\r\n  - Read mode will save CSV output\r\n  - Test and Write modes will look for files to apply to MXE.")
parser.add_argument("-s", "--single-csv", type=str, help="Path to a single CSV file. Test and Write modes will apply this one file to MXE.\r\nIf both -d and -s are specified, directory is applied first, and then single file on top")
parser.add_argument("-x", "--xlb-path", type=str, help="Path to xlb file with text data to resolve MXE text IDs into human-readable stuff, like character and weapon names. Only 'text_mx.xlb' is currently supported (with horrible hacks).")
parser.add_argument("-q", "--quiet", action="store_true", help="Suppress debug logging write MXE mode")
parser.add_argument("-l", "--log", type=str, help="Path to a debug log file generated when writing MXE.")
parser.add_argument("-c", "--config-file", type=str, help="Path to configuration file. If omitted, hardcoded defaults are used.")
parser.add_argument("-b", "--backup-mxe", action="store_true", help="Back up MXE file when writing it out. Only used with W mode.")

args = parser.parse_args()

if os.path.isdir(args.mxe_path) or os.path.splitext(args.mxe_path)[1] != ".mxe":
    print("Error: specified mxe path is a directory or not an mxe file")
    exit()
mxe_path = args.mxe_path

if args.config_file is None:
    print("No config file specified, using defaults")
else:
    print("Applying config file: " + args.config_file)
    with open(args.config_file) as cfg_json:
        data = json.load(cfg_json)
        for name in MXE_SETTINGS.keys():
            if data['MXE_SETTINGS'][name] is not None:
                MXE_SETTINGS[name] = data['MXE_SETTINGS'][name]
        for name in OUTPUT_MODIFIERS.keys():
            if data['OUTPUT_MODIFIERS'][name] is not None:
                OUTPUT_MODIFIERS[name] = data['OUTPUT_MODIFIERS'][name]

if args.template_csv_path is None:
    template_path=os.path.join(os.path.dirname(args.mxe_path),'VlMx_entry_templates.csv')
    print("No template specified, defaulting to: " + template_path)
    
if args.csv_dir is None:
    csv_directory=os.path.splitext(args.mxe_path)[0]
    print("No CSV directory specified, defaulting to: " + csv_directory)

if args.single_csv is not None:
    csv_path = args.single_csv
    print("Single CSV path specified: " + args.single_csv)

if args.xlb_path is None:
    xlb_path=os.path.join(os.path.dirname(args.mxe_path),'text_mx.xlb')
    print("No XLB path specified, defaulting to: " + xlb_path)

if args.log is None:
    debug_log=os.path.join(os.path.dirname(args.mxe_path),'write_log.txt')
    print("No log path specified, defaulting to: " + debug_log)

debug = True
if args.quiet:
    debug = False
"""
    Read templates
"""
templates = []
try:
    print("Reading templates from file: " + template_path + "... ", end='')
    templates = readTemplates(template_path)
    print("Done")
except FileNotFoundError:
    print("Error: template file '" + template_path + "' was not found at specfied path.")
    exit()

main_table = []
try:
    print("Reading MXE file:" + mxe_path + "... ", end='')
    main_table = readMXEFile(mxe_path, templates)
    print("Done")
except:
    print("Failed, exiting")
    exit()

if args.mode=="D":
    print("Dummy mode execution. This should be the last message you see.")

# write out CSVs
if args.mode=="R":
    print("Writing data entries to directory: '" + csv_directory + "' ... ")
    try:
        writeMXEtoCSV(main_table, templates, csv_directory, xlb_path)
    except:
        print("Error:", sys.exc_info())
        exit()
    print("Done")
    
# apply CSV to MXE
if args.mode=="W" or args.mode=="T":
    # apply directory
    if(csv_directory != ""):
        print("Applying CSV dir " + csv_directory + " to mxe in-memory")
        try:
            applyCSVDIRtoMXE(main_table,templates, csv_directory)
        except:
            print("Error:", sys.exc_info())
            exit()
    # apply single CSV
    if(csv_path != ""):
        print("Applying single CSV " + csv_path + " to mxe in-memory")
        try:
            applyCSVtoMXE(main_table,templates, csv_path)
        except:
            print("Error:", sys.exc_info())
            exit()
    
# Write MXE out to the file
if args.mode=="W":
    print("Writing data entries to mxe: '" + mxe_path)
    try:
        writeMXEFile(mxe_path, main_table, templates, MXE_SETTINGS, args.backup_mxe, debug, debug_log)
    except:
        print("Error:", sys.exc_info())
        exit()