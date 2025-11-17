###############################
#   Converted to Python 3.11  #
#   Original author: Frankelstner
#   Converted by ChatGPT
###############################

"""
Usage:
    python dbx_py3.py file1.dbx file2.xml folder_with_files
The script converts .dbx -> .xml and .xml -> .dbx. Drop files or pass paths as arguments.
"""

from __future__ import annotations
import os
import sys
from struct import unpack, pack
from binascii import hexlify, unhexlify
from io import BytesIO
from collections import OrderedDict

TABLEN = "\t"  # adjust indentation level for the xml file

XMLHEADER = "<?xml version=\"1.0\"?>\r\n"

HALVES = ("SphereKeyW", "SphereKeyY", "SphereKeyZ", "TargetId", "SourceId", "SphereKeyX")
DOUBLES = ("AwareForgetTime", "LineOfSightTestTime", "SensingTimeSpan", "FireKeepTime", "LostForgetTime",
           "TimeUntilUnseenIsLost", "AttackerTrackTime")

# hashes are always integer
HASHES = ("OriginalHashedWaveName", "HashedName", "HashedWaveName", "OnRoadMaterialNameHashes", "Hash", "Id",
          "CompositeMeshPartNames")
TYPE2 = ("Name", "TextureFile", "LocationName")
# these are numbers yet their content may consist of exactly 0 numbers. Basically a null-dimensional vector.
EMPTYNUMS = ('NeighbourLinks', 'LeftCurve', 'ForwardGearSpeeds', 'DownCurve', 'CompositeMeshPartNames', 'RandomEventWeight',
             'RightCurve', 'ShCoefficientsLightDelta', 'ShCoefficientsLight', 'FirstPartHealthStateNetworkIds',
             'ReverseGearSpeeds', 'ZOcclusionLookup', 'ForwardGearRatios', 'DisallowedIndices', 'SkinnedMeshTransforms',
             'UpCurve', 'FirstPartHealthStateIndices', 'ShCoefficientsShadow', 'ReverseGearRatios')


def read128(f: BytesIO) -> int:
    """Reads the next few bytes in file-like f as LEB128 and returns an integer"""
    result = 0
    shift = 0
    while True:
        b = f.read(1)
        if not b:
            break
        byte = b[0]
        result |= (byte & 0x7F) << shift
        shift += 7
        if (byte >> 7) == 0:
            break
    return result


def write128(integer: int) -> bytes:
    """Converts an integer to LEB128 and returns a bytes object"""
    if integer == 0:
        return b'\x00'
    out = bytearray()
    while integer:
        byte = integer & 0x7F
        integer >>= 7
        if integer:
            byte |= 0x80
        out.append(byte)
    return bytes(out)


# Try to use external float-to-string lib if present; else fallback to repr
try:
    from ctypes import cdll, c_double, c_char, pointer

    floatlib = cdll.LoadLibrary("floattostring")

    def formatfloat(num):
        bufType = c_char * 100
        buf = bufType()
        bufpointer = pointer(buf)
        floatlib.convertNum(c_double(num), bufpointer, 100)
        raw = bytes(buf.raw)
        rawstring = raw.split(b"\x00", 1)[0].decode('ascii', errors='ignore')
        if rawstring.startswith("-."):
            return "-0." + rawstring[2:]
        elif rawstring.startswith("."):
            return "0." + rawstring[1:]
        elif "e" not in rawstring and "." not in rawstring:
            return rawstring + ".0"
        return rawstring
except Exception:
    def formatfloat(num):
        return repr(float(num))


def intfloat(rawnum: bytes, name: str) -> str:
    """
    rawnum: 4-byte bytes
    Follow original logic: some values must be treated as ints (hashes or small positives or NaN/Inf patterns)
    """
    intnum = unpack(">i", rawnum)[0]
    if name in HASHES:
        return repr(intnum)
    # Simulate original checks:
    # if first byte is 0 (small positive) or exponent all 1s/ -1, treat as int
    first_byte = rawnum[0] & 0xFF
    # original used bitshifts; here approximate: if first byte == 0 -> small positive; if first byte == 0xFF -> possible special
    if (intnum >> 24) == 0 or ((intnum >> 23) in (255, -1)):
        return str(intnum)
    try:
        return formatfloat(unpack(">f", rawnum)[0])
    except Exception:
        return str(intnum)


def toxml(filename: str):
    if not filename.lower().endswith(".dbx"):
        return
    with open(filename, "rb") as fi:
        header = fi.read(8)
        if header != b"{binary}":
            return
        data = fi.read()

    print(filename)
    f = BytesIO(data)  # dump the file in memory
    out = open(filename[:-3] + "xml", "wb")
    out.write(XMLHEADER.encode('utf-8'))
    # offset to PAYLOAD; relative offset is 24 less in original code comment
    totoffset, zero, reloffset, numofstrings = unpack(">IIII", f.read(16))
    stringoffsets = list(unpack(">" + "I" * numofstrings, f.read(4 * numofstrings)))
    # calculate the length of the strings and grab them
    lengths = []
    for i in range(numofstrings - 1):
        lengths.append(stringoffsets[i + 1] - stringoffsets[i])
    lengths.append(reloffset - 4 * numofstrings - stringoffsets[-1])
    strings = []
    for l in lengths:
        raw = f.read(l)
        if raw.endswith(b'\x00'):
            raw = raw[:-1]
        # decode - these are textual strings (tag names/attribute names), preserve robustly
        strings.append(raw.decode('utf-8', errors='replace'))

    # do payload
    tablevel = 0
    opentags = []  # need the prefixes to close the tag, e.g. <array> -> </array>
    try:
        while True:
            # prefixnumber encoded as LEB128
            prefixnumber = read128(f)
            if prefixnumber == 0:
                tablevel -= 1
                closing = (tablevel * TABLEN + "</" + opentags.pop() + ">\r\n")
                out.write(closing.encode('utf-8'))
                continue
            prefix = strings[prefixnumber]
            b = f.read(1)
            if not b:
                break
            hx = hexlify(b).decode('ascii')  # e.g. 'a0' -> first char is 'a', second is hex digit for num attrib
            typ = hx[0]
            # second hex char is number of attributes (a single hex digit)
            numofattrib = int(hx[1], 16)

            attribs = [[strings[read128(f)], strings[read128(f)]] for _ in range(numofattrib)]
            if numofattrib:
                tag = tablevel * TABLEN + "<" + prefix + " " + " ".join([attrib[0] + '="' + attrib[1] + '"' for attrib in attribs])
            else:
                tag = tablevel * TABLEN + "<" + prefix

            if typ == "a":  # contains other elements
                f.seek(1, 1)  # null in original
                tablevel += 1
                opentags.append(prefix)
                out.write((tag + ">\r\n").encode('utf-8'))

            elif typ == "2":
                content = strings[read128(f)]
                if content:
                    out.write((tag + ">" + content + "</" + prefix + ">\r\n").encode('utf-8'))
                else:
                    out.write((tag + " />\r\n").encode('utf-8'))

            elif typ == "7":
                numofnums = read128(f)
                numlength = read128(f)
                if numlength == 4:
                    # need to go through every single number and evaluate whether int or float
                    if numofnums % 4 == 0 and numofnums:
                        contentlist = [None] * numofnums
                        # go through fourth, eighth... element and check if it is always 00 or cd
                        numtype = 0
                        rawnums = [f.read(4) for _ in range(numofnums)]
                        for i in range(3, numofnums, 4):
                            rawnum = rawnums[i]
                            if not numtype:
                                if rawnum == b"\x00\x00\x00\x00":
                                    numtype = 1
                                elif rawnum == b"\xcd\xcd\xcd\xcd":
                                    numtype = 2
                            elif numtype == 1 and rawnum != b"\x00\x00\x00\x00":
                                numtype = 666
                                break
                            elif numtype == 2 and rawnum != b"\xcd\xcd\xcd\xcd":
                                numtype = 666
                                break
                        # run through all nums now
                        if numtype == 1:
                            for i in range(numofnums):
                                if i % 4 == 3:
                                    contentlist[i] = "*zero*"
                                else:
                                    contentlist[i] = intfloat(rawnums[i], attribs[0][1])
                        elif numtype == 2:
                            for i in range(numofnums):
                                if i % 4 == 3:
                                    contentlist[i] = "*nonzero*"
                                else:
                                    contentlist[i] = intfloat(rawnums[i], attribs[0][1])
                        else:
                            contentlist = [intfloat(rawnum, attribs[0][1]) for rawnum in rawnums]

                        content = "/".join(contentlist)
                    else:
                        lst = [intfloat(f.read(4), attribs[0][1]) for _ in range(numofnums)]
                        content = "/".join(lst)

                elif numlength == 8:
                    vals = unpack(">" + "d" * numofnums, f.read(8 * numofnums))
                    content = "/".join([repr(x) for x in vals])
                else:
                    vals = unpack(">" + "H" * numofnums, f.read(2 * numofnums))
                    content = "/".join([repr(x) for x in vals])
                out.write((tag + ">" + content + "</" + prefix + ">\r\n").encode('utf-8'))

            else:  # typ == "6" or other single-byte booleans/numbers
                f.seek(1, 1)  # original did f.seek(1,1) #\x01
                bol = f.read(1)
                if bol == b"\x01":
                    content = "true"
                elif bol == b"\x00":
                    content = "false"
                else:
                    # Could be small integer (e.g. ChannelCount)
                    content = str(bol[0])
                out.write((tag + ">" + content + "</" + prefix + ">\r\n").encode('utf-8'))
    except Exception:
        f.close()
        out.close()


# Functions for writing dbx (xml -> dbx)
def todic_init():
    # returns a fresh dict mapping string->offsetbytes ; original stored offsets as write128(len(dic))
    d = OrderedDict()
    d[""] = b'\x00'  # same as original
    return d


def todic_get(dic: OrderedDict, word: str) -> bytes:
    # returns bytes LEB128 pointer for 'word', adding if missing
    if word in dic:
        return dic[word]
    val = write128(len(dic))
    dic[word] = val
    return val


def readline(line: str, dic: OrderedDict):
    """
    parse one xml line (string) and return bytes to write to payload
    Mirrors original logic but adapted for Python3 strings/bytes.
    """
    line = line.rstrip("\r\n")
    if not line:
        return b""
    tagstart = line.find("<") + 1
    tagend = line.find(">", tagstart)
    if tagstart <= 0 or tagend == -1:
        return None
    if line[tagstart] == "/":
        return b"\x00"  # ENDER

    tag = line[tagstart:tagend]
    prefixlen = tag.find(" ")
    attribs = []
    if prefixlen == -1:
        prefixbytes = todic_get(dic, tag.strip(" /"))
    else:
        prefix = tag[:prefixlen]
        prefixbytes = todic_get(dic, prefix)
        stuff = tag[prefixlen + 1:].split('"')
        # stuff like: name="value" other="v2" -> split by '"' gives pairs
        for i in range(0, len(stuff) - 1, 2):
            left = stuff[i].strip()
            if left.endswith('='):
                key = left[:-1].strip()
            else:
                # fallback
                key = left.split('=')[0].strip()
            val = stuff[i + 1]
            attribs.append((key, val))
    numofattribs = len(attribs)
    attribbytes = b"".join([todic_get(dic, a) for pair in attribs for a in pair])

    # self-closing tag?
    if line[tagend - 1] == "/":
        # prefix + typ '2' with numofattribs and attribbytes and null content
        return prefixbytes + unhexlify(("2%X" % numofattribs).encode('ascii')) + attribbytes + b"\x00"

    contentend = line.rfind("<", tagend + 1)
    if contentend == -1:
        # TYPE A (contains other elements)
        return prefixbytes + unhexlify(("a%X" % numofattribs).encode('ascii')) + attribbytes + b"\x00"

    content = line[tagend + 1:contentend]
    # if numofattribs!=1 or attribs[0][0] not "name" or attribs[0][1] in TYPE2:
    if not (numofattribs == 1 and attribs[0][0] == "name" and attribs[0][1] not in TYPE2):
        return prefixbytes + unhexlify(("2%X" % numofattribs).encode('ascii')) + attribbytes + todic_get(dic, content)

    # from here: numofattribs == 1 and attribs[0][0] == "name" and attribs[0][1] not in TYPE2
    # TYPE 6:
    if content == "true":
        return prefixbytes + b"\x61" + attribbytes + b"\x01\x01"
    elif content == "false":
        return prefixbytes + b"\x61" + attribbytes + b"\x01\x00"
    elif attribs[0][1] == "ChannelCount":
        return prefixbytes + b"\x61" + attribbytes + b"\x01" + pack("B", int(content))

    # Types 2 and 7 (numbers or strings)
    if len(content) == 0:
        if attribs[0][1] in EMPTYNUMS:
            return prefixbytes + b"\x71" + attribbytes + b"\x00\x04"
        else:
            return prefixbytes + unhexlify(("2%X" % numofattribs).encode('ascii')) + attribbytes + b"\x00"

    numstrings = content.split("/")
    # HALVES -> unsigned shorts
    if attribs[0][1] in HALVES:
        try:
            nums = [pack(">H", int(x)) for x in numstrings]
            numlen = b"\x02"
        except Exception:
            print("Invalid short int: {} = {}".format(attribs[0][1], content))
            return None
    elif attribs[0][1] in DOUBLES:
        try:
            nums = [pack(">d", float(x)) for x in numstrings]
            numlen = b"\x08"
        except Exception:
            print("Invalid double float: {} = {}".format(attribs[0][1], content))
            return None
    elif attribs[0][1] in HASHES:
        # try ints, else store as string (type 2)
        try:
            nums = [pack(">i", int(x)) for x in numstrings]
            numlen = b"\x04"
        except Exception:
            if attribs[0][1] == "Id":
                # can be string
                return prefixbytes + unhexlify(("2%X" % numofattribs).encode('ascii')) + attribbytes + todic_get(dic, content)
            else:
                print("Invalid int for hash field: {} = {}".format(attribs[0][1], content))
                return None
    else:
        nums = []
        for numstring in numstrings:
            if numstring == "*zero*":
                nums.append(b"\x00\x00\x00\x00")
                continue
            elif numstring == "*nonzero*":
                nums.append(b"\xcd\xcd\xcd\xcd")
                continue
            try:
                intnum = int(numstring)
                # original had range checks; keep same constraints
                if (intnum >> 24) == 0 or (intnum >> 23) in (255, -1):
                    nums.append(pack(">i", intnum))
                else:
                    print("Invalid integer: {} = {}".format(attribs[0][1], numstring))
                    return None
            except Exception:
                try:
                    floathex = pack(">f", float(numstring))
                    if floathex[0] == 0 and floathex != b"\x00\x00\x00\x00":
                        print("Float too small: {} = {}".format(attribs[0][1], numstring))
                        return None
                    else:
                        nums.append(floathex)
                except ValueError:
                    # not a numeric -> type 2 (string)
                    return prefixbytes + unhexlify(("2%X" % numofattribs).encode('ascii')) + attribbytes + todic_get(dic, content)
                except Exception:
                    print("Float too large: {} = {}".format(attribs[0][1], numstring))
                    return None
        numlen = b"\x04"

    numofnums = write128(len(nums))
    return prefixbytes + b"\x71" + attribbytes + numofnums + numlen + b"".join(nums)


def todbx(filename: str):
    if not filename.lower().endswith(".xml"):
        return
    with open(filename, "rb") as fi:
        header = fi.read(len(XMLHEADER))
        if header.decode('utf-8', errors='ignore') != XMLHEADER:
            return
        f = BytesIO(fi.read())

    print(filename)
    payload = BytesIO()
    dic = OrderedDict()
    dic[""] = b'\x00'  # same default
    # iterate over decoded lines, but we must decode bytes -> str
    f.seek(0)
    for rawline in f:
        # rawline is bytes; decode using utf-8 with replace
        line = rawline.decode('utf-8', errors='replace')
        if not line.translate({ord('\r'): None, ord('\n'): None, ord(' '): None, ord('\t'): None}):
            continue
        towrite = readline(line, dic)
        if towrite is None:
            print("Aborting due to parse error in line:", line)
            return
        payload.write(towrite)

    out = open(filename[:-3] + "dbx", "wb")
    # build strings block
    stringlist = list(dic.keys())
    strings_bytes = b"\x00".join([s.encode('utf-8') for s in stringlist]) + b"\x00"
    numofstrings = len(dic)
    reloffset = 4 * numofstrings + len(strings_bytes)
    # header: "{binary}" + >IIII (reloffset+24,0,reloffset,numofstrings)
    out.write(b"{binary}" + pack(">IIII", reloffset + 24, 0, reloffset, numofstrings))
    offset = 0
    for entry in stringlist:
        out.write(pack(">I", offset))
        offset += len(entry.encode('utf-8')) + 1
    out.write(strings_bytes)
    out.write(payload.getvalue())
    out.close()


def lp(path: str) -> str:
    # long pathnames on Windows: original prefixed with '\\\\?\\'
    if path.startswith('\\\\?\\'):
        return path
    elif path == "":
        return path
    else:
        # in py3, str is fine
        return '\\\\?\\' + os.path.normpath(path)


def main():
    inp = [lp(p) for p in sys.argv[1:]]
    mode = ""
    for ff in inp:
        if os.path.isfile(ff):
            if ff.lower().endswith(".xml"):
                todbx(ff)
            elif ff.lower().endswith(".dbx"):
                toxml(ff)
        else:
            if not mode:
                mode = input("Convert everything from selected folders to (d)bx or (x)ml\r\n")
            if mode.lower() == "d":
                for dir0, dirs, files in os.walk(ff):
                    for f in files:
                        try:
                            todbx(os.path.join(dir0, f))
                        except Exception as e:
                            print("Error processing", f, ":", e)
            elif mode.lower() == "x":
                for dir0, dirs, files in os.walk(ff):
                    for f in files:
                        try:
                            toxml(os.path.join(dir0, f))
                        except Exception as e:
                            print("Error processing", f, ":", e)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # mimic original behavior: wait for keypress so user can see the error when double-clicking the script
        print("Unhandled exception:", e)
        try:
            input("Press Enter to exit...")
        except Exception:
            pass
