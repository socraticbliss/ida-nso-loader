"""
Nintendo Switch Binary (NSO) loader for IDA

Copyright (C) 2017 jam1garner

Thanks to Reswitched and Switchbrew for info

licensed under the MIT license - see LICENSE file in project
root for more information.
"""

import os,sys,struct
from idaapi import *

#Install lz4 if they don't already have it
try:
    import lz4
except ImportError:
    import pip
    pip.main(['install','lz4'])
    import lz4

def Int32(f):
    return struct.unpack('<L', f.read(4))[0]

def ToInt32(b):
    return struct.unpack('<L', b[:4])[0]

#Based on Mephisto
class SegInfo:
    def __init__(self, f):
        self.fileOffset = Int32(f)
        self.memoryLocation = Int32(f)
        self.decompressedSize = Int32(f)
        self.alignmentOrSize = Int32(f)

#Based on switchbrew NSO page
class MOD0:
    def __init__(self, b):
        padding = ToInt32(b[0:4])
        magicOffset = ToInt32(b[4:8])
        self.magicOffset = magicOffset
        self.magic = ToInt32(b[magicOffset:magicOffset+4])
        self.dynamicOff = ToInt32(b[magicOffset+4:magicOffset+8]) + magicOffset
        self.bssStartOff = ToInt32(b[magicOffset+0x8:magicOffset+0xC]) + magicOffset
        self.bssEndOff = ToInt32(b[magicOffset+0xC:magicOffset+0x10]) + magicOffset
        self.ehFrameHdrStart = ToInt32(b[magicOffset+0x10:magicOffset+0x14]) + magicOffset
        self.ehFrameHdrEnd = ToInt32(b[magicOffset+0x14:magicOffset+0x18]) + magicOffset
        self.moduleOff = ToInt32(b[magicOffset+0x18:magicOffset+0x1C]) + magicOffset
        self.bssSize = self.bssEndOff - self.bssStartOff
        self.ehFrameHdrSize = self.ehFrameHdrEnd - self.ehFrameHdrStart

class NSO:
    def __init__(self, f):
        self.read(f)

    def read(self, f):
        f.seek(0, 2)
        endOfFile = f.tell()
        f.seek(0x10)
        self.textSegment = SegInfo(f)
        self.rodataSegment = SegInfo(f)
        self.dataSegment = SegInfo(f)
        
        #Note: python lz4 library requires the expected decompressed size at the beginning of the compression
        #so I am nice and append it there for it :)
        f.seek(self.textSegment.fileOffset)
        data = struct.pack('<L', self.textSegment.decompressedSize) + f.read(self.rodataSegment.fileOffset - self.textSegment.fileOffset)
        self.textBytes = lz4.block.decompress(data)
        
        f.seek(self.rodataSegment.fileOffset)
        data = struct.pack('<L', self.rodataSegment.decompressedSize) + f.read(self.dataSegment.fileOffset - self.rodataSegment.fileOffset)
        self.rodataBytes = lz4.block.decompress(data)
        
        f.seek(self.dataSegment.fileOffset)
        data = struct.pack('<L', self.dataSegment.decompressedSize) + f.read(endOfFile - self.dataSegment.fileOffset)
        self.dataBytes = lz4.block.decompress(data)

        self.mod0 = MOD0(self.textBytes)


    #Not used for loader, just for looking at stuff in a better hex view than IDA's
    def dump(self):
        size = 0
        if self.textSegment.memoryLocation + len(self.textBytes) > size:
            size = self.textSegment.memoryLocation + len(self.textBytes)
        if self.rodataSegment.memoryLocation + len(self.rodataBytes) > size:
            size = self.rodataSegment.memoryLocation + len(self.rodataBytes)
        if self.dataSegment.memoryLocation + len(self.dataBytes) > size:
            size = self.dataSegment.memoryLocation + len(self.dataBytes)

        with open('nso_dump.bin', 'wb') as f:
        	f.write(size * chr(0))
        	f.seek(self.textSegment.memoryLocation)
        	f.write(self.textBytes)
        	f.seek(self.rodataSegment.memoryLocation)
        	f.write(self.rodataBytes)
        	f.seek(self.dataSegment.memoryLocation)
        	f.write(self.dataBytes)

def load_file(f, neflags, format):
    set_processor_type("arm", SETPROC_ALL|SETPROC_FATAL)
    SetShortPrm(idc.INF_LFLAGS, idc.GetShortPrm(idc.INF_LFLAGS) | idc.LFLG_64BIT)

    #Read in file
    nso = NSO(f)

    # add text segment
    mem2base(nso.textBytes, nso.textSegment.memoryLocation)
    add_segm(0, nso.textSegment.memoryLocation, nso.textSegment.memoryLocation+len(nso.textBytes), '.text', "CODE")
    set_segm_addressing(get_segm_by_name(".text"), 2)

    mem2base(nso.rodataBytes, nso.rodataSegment.memoryLocation)
    add_segm(0, nso.rodataSegment.memoryLocation, nso.rodataSegment.memoryLocation+len(nso.rodataBytes), '.rodata', "CONST")

    mem2base(nso.dataBytes, nso.dataSegment.memoryLocation)
    add_segm(0, nso.dataSegment.memoryLocation, nso.dataSegment.memoryLocation+len(nso.dataBytes), '.data', "DATA")

    mem2base(chr(0) * nso.mod0.bssSize, nso.mod0.bssStartOff)
    add_segm(0, nso.mod0.bssStartOff, nso.mod0.bssEndOff, '.bss', 'BSS')

    add_segm(0, nso.mod0.ehFrameHdrStart,  nso.mod0.ehFrameHdrEnd, '.eh_frame_hdr', 'CONST')

    return 1

def accept_file(f, n):
    retval = 0

    if n == 0:
        f.seek(0)
        if struct.unpack('>I', f.read(4))[0] == 0x4E534F30:
            retval = "Nintendo Switch Binary (NSO)"

    return retval

# if __name__ == "__main__":
# 	with open("G:/main", 'rb') as f:
# 		nso = NSO(f)
# 		nso.dump()