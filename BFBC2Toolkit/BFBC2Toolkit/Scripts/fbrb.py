###############################
#   Converted to Python 3.11  #
#   Based on original by Frankelstner
#   Lightly improved, logic preserved
###############################

import os
import sys
import gzip
import tempfile
from struct import pack, unpack
from io import BytesIO

# packing parameters
compressionlevel = 1     # 0–9 (0 = no compression)
packtmpfile = 1          # temporary file on disk for packing
unpacktmpfile = 0        # temporary file for unpacking

unpackfolder = ""
packfolder = ""
BUFFSIZE = 1_000_000     # 1 MB buffer

# Dump buffer used by unpacker
dump = None


def makeint(num: int) -> bytes:
    return pack(">I", num)


def readint(pos: int) -> int:
    return unpack(">I", dump[pos:pos+4])[0]


def grabstring(offset: int) -> str:
    """
    Reads a null-terminated string from global 'dump'.
    Python 2 code used characters, now we use bytes.
    """
    out = bytearray()
    while dump[offset] != 0:
        out.append(dump[offset])
        offset += 1
    return out.decode("utf-8", errors="replace")

# соответствие расширений (как в оригинале)
dic = dict(
    swfmovie='SwfMovie', dx10pixelshader='Dx10PixelShader', havokphysicsdata='HavokPhysicsData',
    treemeshset='TreeMeshSet', terrainheightfield='TerrainHeightfield', itexture='ITexture', animtreeinfo='AnimTreeInfo',
    irradiancevolume='IrradianceVolume', visualterrain='VisualTerrain', skinnedmeshset='SkinnedMeshSet',
    dx10vertexshader='Dx10VertexShader', aimanimation='AimAnimation', occludermesh='OccluderMesh',
    dx9shaderdatabase='Dx9ShaderDatabase', wave='Wave', sootmesh='SootMesh', terrainmaterialmap='TerrainMaterialMap',
    rigidmeshset='RigidMeshSet', compositemeshset='CompositeMeshSet', watermesh='WaterMesh', visualwater='VisualWater',
    dx9vertexshader='Dx9VertexShader', dx9pixelshader='Dx9PixelShader', dx11shaderdatabase='Dx11ShaderDatabase',
    dx11pixelshader='Dx11PixelShader', grannymodel='GrannyModel', ragdollresource='RagdollResource',
    grannyanimation='GrannyAnimation', weathersystem='WeatherSystem', dx11vertexshader='Dx11VertexShader', terrain='Terrain',
    impulseresponse='ImpulseResponse', binkmemory='BinkMemory', deltaanimation='DeltaAnimation',
    dx10shaderdatabase='Dx10ShaderDatabase', meshdata='MeshData', xenonpixelshader='XenonPixelShader',
    xenonvertexshader='XenonVertexShader', xenonshaderdatabase='XenonShaderDatabase', xenontexture='XenonTexture',
    ps3pixelshader='Ps3PixelShader', ps3vertexshader='Ps3VertexShader', ps3shaderdatabase='Ps3ShaderDatabase',
    ps3texture='Ps3Texture', pathdatadefinition='PathDataDefinition',
    nonres='<non-resource>', dbx='<non-resource>', dbxdeleted='*deleted*', resdeleted='*deleted*', bin='<non-resource>',
    dbmanifest='<non-resource>'
)


def packer(sourcefolder: str, targetfile: str = "", compressionlevel_param: int = None, tmpfile: int = None):
    """
    Pack a folder that ends with " FbRB" into a .fbrb archive.
    Logic kept as original; improved bytes handling.
    """
    global compressionlevel, packtmpfile
    if compressionlevel_param is None:
        compressionlevel_param = compressionlevel
    if tmpfile is None:
        tmpfile = packtmpfile

    sourcefolder = lp(sourcefolder)
    if not os.path.isdir(sourcefolder) or not sourcefolder.endswith(" FbRB"):
        return

    # Print like original (skip first 4 chars like original did)
    try:
        print(sourcefolder[4:])
    except Exception:
        print(sourcefolder)

    toplevellength = len(sourcefolder) + 1  # for relative paths (original behavior)

    if not targetfile:
        targetfile = sourcefolder[:-5] + ".fbrb"
    else:
        targetfile = lp(targetfile) + ".fbrb"

    # strings block (bytes), ext dictionary and entries block (bytes)
    strings_bytes = bytearray()
    extdic = {}  # ext string -> position in strings_bytes
    entries = bytearray()
    numofentries = 0
    payloadoffset = 0  # uncompressed payload length so far

    # Prepare payload writer (s2). Use temp file if requested.
    if tmpfile:
        s2 = tempfile.TemporaryFile()
    else:
        s2 = BytesIO()

    # If we compress payload, write into gzip wrapper around s2
    if compressionlevel_param:
        zippy2 = gzip.GzipFile(fileobj=s2, mode="wb", compresslevel=compressionlevel_param, filename="")
    else:
        zippy2 = None

    # walk through folder
    for dir0, dirs, files in os.walk(sourcefolder):
        # keep original code's use of backslash terminated dir
        dir_with_slash = dir0 + "\\"
        for fname in files:
            rawfilename, extension = os.path.splitext(fname)
            extension = extension[1:].lower()
            try:
                ext = dic[extension]
            except KeyError:
                # skip unknown extensions (original behavior)
                continue

            numofentries += 1

            # restore filename strings to res, dbx, bin, dbmanifest; null terminated
            if extension == "dbxdeleted":
                filepath = dir_with_slash.replace("\\", "/")[toplevellength:] + fname[:-7] + "\x00"
            elif extension not in ("dbx", "bin", "dbmanifest"):
                filepath = dir_with_slash.replace("\\", "/")[toplevellength:] + rawfilename + ".res\x00"
            else:
                filepath = dir_with_slash.replace("\\", "/")[toplevellength:] + fname + "\x00"

            # stringoffset is current length of strings_bytes (as 4-byte big-endian)
            stringoffset_bytes = makeint(len(strings_bytes))
            # append filepath as bytes
            if isinstance(filepath, str):
                filepath_b = filepath.encode("utf-8", errors="replace")
            else:
                filepath_b = bytes(filepath)
            strings_bytes.extend(filepath_b)

            # file length and deleteflag
            fullpath = os.path.join(dir0, fname)
            filelength = os.path.getsize(fullpath)
            if filelength == 0:
                deleteflag = b"\x00\x00\x00\x00"
            else:
                deleteflag = b"\x00\x01\x00\x00"

            # check ext position (store ext strings into strings_bytes to avoid duplicates)
            if ext in extdic:
                extpos = extdic[ext]
            else:
                extpos = len(strings_bytes)
                extdic[ext] = extpos
                ext_b = (ext + "\x00").encode("utf-8", errors="replace")
                strings_bytes.extend(ext_b)

            # make the 24-byte entry: stringoffset(4) + deleteflag(4) + payloadoffset(4) + 2*filelength(4+4) + extpos(4)
            # Note: original wrote 2*makeint(filelength) (two copies). We'll replicate exactly.
            entries.extend(stringoffset_bytes)
            entries.extend(deleteflag)
            entries.extend(makeint(payloadoffset))
            entries.extend(makeint(filelength))
            entries.extend(makeint(filelength))  # duplicate as original
            entries.extend(makeint(extpos))

            payloadoffset += filelength

            # read file content and write to payload (possibly compressed)
            with open(fullpath, "rb") as f1:
                data = f1.read()
                if zippy2:
                    zippy2.write(data)
                else:
                    # s2 is BytesIO or TemporaryFile
                    s2.write(data)

    # finalize payload compression if used
    if zippy2:
        zippy2.close()
        zippedflag = b"\x01"
    else:
        zippedflag = b"\x00"

    # Build part1 (uncompressed): header 0x00000002 + length(strings) + strings + numofentries + entries + zippedflag + payloadoffset
    part1_prefix = b"\x00\x00\x00\x02"
    part1 = bytearray()
    part1.extend(part1_prefix)
    part1.extend(makeint(len(strings_bytes)))
    part1.extend(strings_bytes)
    part1.extend(makeint(numofentries))
    part1.extend(entries)
    part1.extend(zippedflag)
    part1.extend(makeint(payloadoffset))

    # compress part1 into gzip (original did that)
    s1 = BytesIO()
    with gzip.GzipFile(fileobj=s1, mode="wb", compresslevel=1) as gz:
        gz.write(bytes(part1))
    output = s1.getvalue()
    s1.close()

    # write final file: header "FbRB" + len(output) + output + payload (from s2)
    with open(targetfile, "wb") as out:
        out.write(b"FbRB")
        out.write(makeint(len(output)))
        out.write(output)
        # write payload from s2
        if tmpfile:
            s2.seek(0)
            while True:
                buff = s2.read(BUFFSIZE)
                if buff:
                    out.write(buff)
                else:
                    break
            s2.close()
        else:
            # s2 is BytesIO
            s2.seek(0)
            out.write(s2.read())
            s2.close()

# ---------------------------
# Часть 3/4 — unpacker(), lp(), main()
# ---------------------------

def unpacker(sourcefilename: str, targetfolder: str = "", tmpfile: int = None):
    """
    Unpack a .fbrb archive into a folder ending with ' FbRB'.
    Logic kept as original; bytes handling fixed for Python 3.
    """
    global dump
    if tmpfile is None:
        tmpfile = unpacktmpfile

    sourcefilename = lp(sourcefilename)
    if not sourcefilename.lower().endswith(".fbrb"):
        return

    with open(sourcefilename, "rb") as f:
        header = f.read(4)
        if header != b"FbRB":
            return
        # print like original (skip first 4 chars if possible)
        try:
            print(sourcefilename[4:])
        except Exception:
            print(sourcefilename)

        cut_bytes = f.read(4)
        if len(cut_bytes) < 4:
            return
        cut = unpack(">I", cut_bytes)[0]

        part1_bytes = f.read(cut)
        # read remaining as part2 (either into temp file or BytesIO)
        if tmpfile:
            part2 = tempfile.TemporaryFile()
            # read rest in chunks to avoid memory spike
            while True:
                chunk = f.read(BUFFSIZE)
                if not chunk:
                    break
                part2.write(chunk)
            part2.seek(0)
        else:
            part2_bytes = f.read()
            part2 = BytesIO(part2_bytes)

    # decompress gzip parts
    part1 = BytesIO(part1_bytes)
    with gzip.GzipFile(mode="rb", fileobj=part1) as gz1:
        dump = gz1.read()
    part1.close()

    # open second gzip (payload) as fileobj
    if tmpfile:
        zippy2 = gzip.GzipFile(mode="rb", fileobj=part2)
    else:
        # part2 is BytesIO containing possibly compressed payload
        zippy2 = gzip.GzipFile(mode="rb", fileobj=part2)

    # determine zipped flag: original checked dump[-5] == "\x00"
    # Now check byte value safely
    if len(dump) >= 5 and dump[-5] == 0:
        zipped = 0
    else:
        zipped = 1

    # helper readint uses global 'dump'
    strlen = readint(4)
    numentries = readint(strlen + 8)

    for i in range(numentries):
        filenameoffset = readint(strlen + 12 + i * 24)
        # undeleteflag = readint(strlen+16+i*24)  # unused
        payloadoffset = readint(strlen + 20 + i * 24)
        payloadlen = readint(strlen + 24 + i * 24)
        # payloadlen2 = readint(strlen+28+i*24)  # unused
        extensionoffset = readint(strlen + 32 + i * 24)

        # get folder/name and extension
        fname_full = grabstring(filenameoffset + 8)
        folder, filename = os.path.split(fname_full)
        name, ending = os.path.splitext(filename)
        extension = grabstring(extensionoffset + 8).lower()

        if extension == "*deleted*":
            if ending == ".dbx":
                ending = ".dbxdeleted"
            else:
                ending = ".resdeleted"
        elif extension == "<non-resource>" and ending == ".res":
            ending = ".nonres"
        elif extension != "<non-resource>":
            ending = "." + extension

        finalpath = targetfolder if targetfolder else sourcefilename[:-5] + " FbRB\\"
        finalpath = lp(finalpath)
        finalpath = os.path.join(finalpath, folder.replace("/", "\\"))
        if folder != "":
            # ensure trailing slash isn't duplicated; os.path.join handles it
            pass

        if not os.path.isdir(finalpath):
            os.makedirs(finalpath, exist_ok=True)

        outpath = os.path.join(finalpath, name + ending)
        # write payload from second gzip/file
        with open(outpath, "wb") as out:
            if zipped:
                # payload is in the gzip stream zippy2
                zippy2.seek(payloadoffset)
                out.write(zippy2.read(payloadlen))
            else:
                # payload is raw in part2
                part2.seek(payloadoffset)
                out.write(part2.read(payloadlen))

    zippy2.close()
    if tmpfile:
        part2.close()


def lp(path: str) -> str:
    """
    Long path handling (keeps original behavior of prefixing with '\\\\?\\' on Windows-like paths).
    """
    if not path:
        return path
    if path.startswith('\\\\?\\'):
        return path
    # Normalize path using os.path.normpath to remove redundant separators
    # Only prefix on Windows; but original always prefixed, so we keep similar behavior
    try:
        return '\\\\?\\' + os.path.normpath(path)
    except Exception:
        return path


def main():
    inp = [lp(p) for p in sys.argv[1:]]
    mode = ""
    for ff in inp:
        print("Processing:", ff)
        if os.path.isdir(ff) and ff.endswith(" FbRB"):
            print("Packing folder:", ff)
            packer(ff, packfolder, compressionlevel, packtmpfile)
        elif os.path.isfile(ff):
            print("Unpacking file:", ff)
            unpacker(ff, unpackfolder, unpacktmpfile)
        else:
            print("Folder does not match specific pattern:", ff)
            if not mode:
                mode = input("(u)npack or (p)ack everything from selected folder(s)\r\n")
            print("Mode selected:", mode)
            if mode.lower() == "u":
                for dir0, dirs, files in os.walk(ff):
                    for f in files:
                        try:
                            print("Unpacking:", f)
                            unpacker(os.path.join(dir0, f), unpackfolder, unpacktmpfile)
                        except Exception as e:
                            print("Error unpacking", f, "->", e)

            elif mode.lower() == "u":
                for dir0, dirs, files in os.walk(ff):
                    if not files:
                        print("No files found in:", dir0)
                        continue
                    for f in files:
                        full_path = os.path.join(dir0, f)
                        print("Found file:", full_path)
                        try:
                            # здесь можно добавить проверку расширения, если unpacker работает только с определёнными файлами
                            if f.lower().endswith(".fbrb"):  # пример фильтра, измените под свои нужды
                                print("Unpacking:", full_path)
                                unpacker(full_path, unpackfolder, unpacktmpfile)
                            else:
                                print("Skipping (not .fbrb):", full_path)
                        except Exception as e:
                            print("Error unpacking", full_path, "->", e)

            elif mode.lower() == "p":
                for dir0, dirs, files in os.walk(ff):
                    for f in files:
                        try:
                            print("Packing:", f)
                            packer(os.path.join(dir0, f), packfolder, compressionlevel, packtmpfile)
                        except Exception as e:
                            print("Error packing", f, "->", e)
            else:
                print("Invalid mode, skipping folder:", ff)



if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Unhandled exception:", e)
        try:
            input("Press Enter to exit...")
        except Exception:
            pass
