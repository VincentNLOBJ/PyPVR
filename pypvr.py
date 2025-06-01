import numpy as np
import os
import re
import sys
import math
import time
import io
import struct
import zlib
import fnmatch
from PIL import Image

'''
MIT License

Copyright (c) 2025 VincentNL

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

-----

PyPVR is a modern Python tool for encoding / decoding PowerVR2 images used by SEGA Naomi and SEGA Dreamcast.
All texture modes, pixel formats, palettes and PVR variations used by SEGA's SDK are supported.

--------
CREDITS
--------

 - Rob2d for K-means idea leading to quality VQ encoding
 - Egregiousguy for YUV420 decoding 
 - Kion for SmallVQ mipmaps data
 - MetalliC for hardware knowledge
 - tvspelsfreak for SR conversion to normal map

Testing:
 - Esppiral
 - Alexvgz
 - PkR
 - Derek (ateam) 
 - dakrk
 - neSneSgB
 - woofmute
 - TVi
 - Sappharad
'''

class Pypvr:
    px_modes = {
        0: '1555',  # ARGB1555
        1: '565',  # RGB565
        2: '4444',  # ARGB4444
        3: 'yuv422',  # YUV422
        4: 'bump',  # SR Height map
        5: '555',  # RGB555 - PCX only
        6: 'yuv420',  # YUV420 - same as .SAN format
        7: '8888',  # RGBA8888
        8: 'p4bpp',  # Placeholder 4bpp, pixel format in .PVP file
        9: 'p8bpp',  # Placeholder 8bpp, pixel format in .PVP file
    }

    tex_modes = {
        1: 'tw',  # Twiddled
        2: 'tw mm',  # Twiddled Mips
        3: 'vq',  # VQ
        4: 'vq mm',  # VQ Mips
        5: 'pal4',  # Palette4
        6: 'pal4 mm',  # Palette4 Mips
        7: 'pal8',  # Palette8
        8: 'pal8 mm',  # Palette8 Mips
        9: 're',  # Rectangle
        10: 're mm',  # Reserved - Rectangle can't be mipmapped
        11: 'st',  # Stride
        12: 'st mm',  # Reserved - Stride can't be mipmapped, using "re mm"
        13: 'twre',  # Twiddled Rectangle
        14: 'bmp',  # Bitmap
        15: 'bmp mm',  # Bitmap Mips
        16: 'svq',  # SmallVQ
        17: 'svq mm',  # SmallVQ Mips
        18: 'twal mm'  # Twiddled Alias Mips
    }

    # common twiddle table, there might be better methods but it's fast.
    def twiddle(self, w, h):
        # initialize variables
        index = 0
        arr, h_arr = [], []
        h_inc = Pypvr().init_table()

        # rectangle (horizontal)
        if w > h:
            ratio = int(w / h)

            # print(f'width is {ratio} times height!')

            if w % 32 == 0 and w & (w - 1) != 0 or h & (h - 1) != 0:
                # print('h and w not power of 2. Using Stride format')
                n = h * w
                for i in range(n):
                    arr.append(i)
            else:
                # single block h_inc length
                cur_h_inc = {w: h_inc[0:h - 1] + [2]}  # use height size to define repeating block h_inc

                # define the first horizontal row of image pixel array:
                for j in range(ratio):
                    if w in cur_h_inc:
                        for i in cur_h_inc[w]:
                            h_arr.append(index)
                            index += i
                    index = (len(h_arr) * h)

                # define the vertical row of image pixel array of repeating block:
                v_arr = [int(x / 2) for x in h_arr]
                v_arr = v_arr[0:h]

                for val in v_arr:
                    arr.extend([x + val for x in h_arr])

        # rectangle (vertical)
        elif h > w:
            ratio = int(h / w)
            # print(f'height is {ratio} times width!')

            # set the size of pixel increase array
            cur_h_inc = {w: h_inc[0:w - 1] + [2]}

            # define the first horizontal row of image pixel array:
            if w in cur_h_inc:
                for i in cur_h_inc[w]:
                    h_arr.append(index)
                    index += i

            # define the vertical row of image pixel array:
            v_arr = [int(x / 2) for x in h_arr]

            # repeat vertical array block from the last value of array * h/w ratio
            for i in range(ratio):
                if i == 0:
                    last_val = 0
                else:
                    last_val = arr[-1] + 1

                for val in v_arr:
                    arr.extend([last_val + x + val for x in h_arr])

        elif w == h:  # square
            cur_h_inc = {w: h_inc[0:w - 1] + [2]}
            # define the first horizontal row of image pixel array:
            if w in cur_h_inc:
                for i in cur_h_inc[w]:
                    h_arr.append(index)
                    index += i

            # define the vertical row of image pixel array:
            v_arr = [int(x / 2) for x in h_arr]

            for val in v_arr:
                arr.extend([x + val for x in h_arr])

        return arr

    def init_table(self):
        pat2, h_inc = [], []

        # build Twiddle index table
        seq = np.array([2, 6, 2, 22, 2, 6, 2])
        pat = np.concatenate([seq, [86], seq, [342], seq, [86], seq])

        for i in range(4):
            pat2.extend([1366, 5462, 1366, 21846])
            pat2.extend([1366, 5462, 1366, 87382] if i % 2 == 0 else [1366, 5462, 1366, 349526])

        pat2 = np.array(pat2)

        for i in range(len(pat2)):
            h_inc.extend(np.concatenate([pat, [pat2[i]]]))

        return h_inc

    class Decode:
        def __init__(self, args_str=None, buff_pvr=None, buff_pvp=None):
            self.files_lst = []
            self.out_dir = None
            self.fmt = "png"
            self.flip = ""
            self.log = True
            self.silent = False
            self.debug = False
            self.crc_value = None
            self.log_content = ''
            self.buffer_mode = False
            self.nopvp = False
            self.usepal = None
            self.act_export = False

            self.buffer_pvr = buff_pvr
            self.buffer_pvp = buff_pvp
            self.image_buffer = None

            if args_str:
                # first, check for usepal before processing any other files
                usepal_pattern = r'-usepal\s+"?([^\s"]+\.pvp)"?|"?([^\s"]+\.pvp)"?'
                usepal_match = re.search(usepal_pattern, args_str)
                if usepal_match:
                    self.usepal = usepal_match.group(1) or usepal_match.group(2)
                    # remove the -usepal argument and its value from args_str
                    args_str = re.sub(r'-usepal\s+"?[^\s"]+\.pvp"?\s*', '', args_str)

                # all other patterns
                file_pattern = r'"([^"]+\.(?:pvr|pvp|dat|bin|pvm|tex|mun))"|([^\s]+\.(?:pvr|pvp|dat|bin|pvm|tex|mun))'
                fmt_pattern = r'-fmt\s+(\w+)'
                out_dir_pattern = r'-o\s+"?([^"\s]+(?:\s+[^"\s]+)*)"?'
                flip_pattern = r'-flip'
                silent_flag_pattern = r'-silent'
                nolog_flag_pattern = r'-nolog'
                dbg_flag_pattern = r'-dbg'
                act_flag_pattern = r'-act'
                buffer_pattern = r'-buffer'
                nopvp_pattern = r'-nopvp'

                # extract filenames (PVR or PVP files)
                matches = re.findall(file_pattern, args_str, re.IGNORECASE)
                # non-empty match groups, excluding the usepal file
                self.files_lst = [m[0] if m[0] else m[1] for m in matches if
                                  (m[0] if m[0] else m[1]) != self.usepal]

                fmt_match = re.search(fmt_pattern, args_str)
                if fmt_match:
                    self.fmt = fmt_match.group(1)

                out_dir_match = re.search(out_dir_pattern, args_str)
                if out_dir_match:
                    self.out_dir = out_dir_match.group(1).strip()
                    if not os.path.isabs(self.out_dir):
                        self.out_dir = os.path.abspath(self.out_dir)

                if re.search(flip_pattern, args_str):
                    self.flip = True

                if re.search(silent_flag_pattern, args_str):
                    self.silent = True

                if re.search(nolog_flag_pattern, args_str):
                    self.log = False

                if re.search(dbg_flag_pattern, args_str):
                    self.debug = True

                if re.search(buffer_pattern, args_str):
                    self.buffer_mode = True

                if re.search(nopvp_pattern, args_str):
                    self.nopvp = True

                if re.search(act_flag_pattern, args_str):
                    self.act_export = True

            # if no output directory is specified, default to the directory of the first file
            if not self.out_dir and self.files_lst:
                self.out_dir = os.path.abspath(os.path.dirname(self.files_lst[0]))

            # ensure the output directory exists
            if self.out_dir and not self.buffer_mode:
                os.makedirs(self.out_dir, exist_ok=True)

            # debug info
            if self.debug:
                print(f"Files: {self.files_lst}")
                print(f"Output Directory: {self.out_dir}")
                print(f"Format: {self.fmt}")
                print(f"Flip: {self.flip}")
                print(f"Log: {self.log}")
                print(f"Silent: {self.silent}")
                print(f"Debug: {self.debug}")
                print(f"Buffer: {self.buffer_mode}")
                print(f"USE PVP: {self.usepal}")
                print(f"NO PVP: {self.nopvp}")
                print(f"ACT Export: {self.act_export}")


            if self.buffer_mode and self.buffer_pvr:

                if self.buffer_pvp:
                    act_buffer = self.load_pvp(None, bytearray(), None,self.buffer_pvp)
                else:
                    act_buffer = bytearray()

                self.load_pvr(None, True if self.buffer_pvp else False, act_buffer,None, self.buffer_pvr)

            else:
                for cur_file in self.files_lst:
                    if not cur_file.lower().endswith(('pvp', 'pvr')):

                        print(f"Scanning {cur_file}")
                        try:
                            with open(cur_file, "rb") as f:
                                self.log = True
                                buffer = f.read()

                                # find PVRT and PVPL offsets
                                pvrt_matches = [match.start() for match in re.finditer(b"PVRT", buffer)]
                                pvpl_matches = [match.start() for match in re.finditer(b"PVPL", buffer)]

                                # lists to store offsets and sizes
                                pvrt_offsets_sizes = []
                                pvpl_offsets_sizes = []

                                pvri = 0
                                pvpi = 0
                                apply_palette = False
                                act_buffer = bytearray()

                                # process PVRT matches
                                for offset in pvrt_matches:
                                    if self.debug: print(f"PVRT found at offset: {hex(offset)}")

                                    if offset + 4 < len(buffer):
                                        filesize = int.from_bytes(buffer[offset + 4:offset + 8], byteorder='little') + 8
                                        remaining_bytes = len(buffer) - offset

                                        if filesize > remaining_bytes or filesize < 0x10:
                                            continue
                                    else:
                                        continue

                                    if offset + 11 < len(buffer):

                                        byte_a = buffer[offset + 0xA]
                                        byte_b = buffer[offset + 0xB]
                                        if byte_a != 0x00 or byte_b != 0x00:
                                            continue
                                    else:
                                        continue

                                    pvrt_offsets_sizes.append((offset, filesize))
                                    unpack_dir = os.path.join(self.out_dir, os.path.basename(cur_file) + '_EXT', 'PVR')
                                    os.makedirs(unpack_dir, exist_ok=True)

                                    full_pvr_path = os.path.join(unpack_dir, f"{str(pvri).zfill(3)}.pvr")

                                    # extract file
                                    with open(full_pvr_path, 'wb') as p:
                                        p.write(buffer[offset:offset + filesize])
                                        pvri += 1

                                    self.log_content += (
                                        f"PVR FILE   : {os.path.normpath(full_pvr_path)}\n"
                                        f"CONTAINER  : {os.path.normpath(cur_file)}\n"
                                        f"DATA OFFST : {offset}\n"
                                        f"DATA FSIZE : {filesize}\n"
                                    )

                                    self.load_pvr(full_pvr_path, apply_palette, act_buffer,
                                                  os.path.join(os.path.basename(cur_file) + '_EXT',
                                                               f"{str(pvri - 1).zfill(3)}.pvr"))


                                # process PVPL matches
                                for offset in pvpl_matches:
                                    self.debug: print(f"PVPL found at offset: {hex(offset)}")

                                    if offset + 0xE + 2 <= len(buffer):
                                        value = int.from_bytes(buffer[offset + 0xE:offset + 0xE + 2],
                                                               byteorder='little')
                                        filesize = int.from_bytes(buffer[offset + 4:offset + 8], byteorder='little') + 8

                                        if value not in {0x10, 0x100}:
                                            continue
                                    else:
                                        continue

                                    pvpl_offsets_sizes.append((offset, filesize))
                                    unpack_dir = os.path.join(self.out_dir, os.path.basename(cur_file) + '_EXT', 'PVP')
                                    os.makedirs(unpack_dir, exist_ok=True)

                                    full_pvp_path = os.path.join(unpack_dir, f"{str(pvpi).zfill(3)}.pvp")

                                    # extract file
                                    with open(os.path.join(unpack_dir, f"{str(pvpi).zfill(3)}.pvp"), 'wb') as p:
                                        p.write(buffer[offset:offset + filesize])
                                        pvpi += 1


                                    act_buffer = bytearray()

                                    self.log_content += (
                                        f"PVP FILE   : {os.path.normpath(full_pvp_path)}\n"
                                        f"CONTAINER  : {os.path.normpath(cur_file)}\n"
                                        f"DATA OFFST : {offset}\n"
                                        f"DATA FSIZE : {filesize}\n"
                                    )
                                    self.load_pvp(full_pvp_path, act_buffer, full_pvp_path)

                                print(f"Finished extracting {cur_file}")


                        except FileNotFoundError:
                            print(f"File not found: {cur_file}")
                        except Exception as e:
                            print(f"Error scanning file {cur_file}: {e}")

                    else:
                        full_pvr_path = os.path.abspath(cur_file[:-4] + '.pvr')

                        if self.usepal:

                            full_pvp_path = os.path.abspath(self.usepal)
                        else:
                            full_pvp_path = os.path.abspath(cur_file[:-4] + '.pvp')

                        # print the paths being checked
                        # if not self.silent: print(f"Processing file: {cur_file}")
                        if self.debug: print(f"Checking PVR file: {full_pvr_path}, PVP file: {full_pvp_path}")

                        # check if PVP or PVR file exists
                        pvp_exists = os.path.exists(full_pvp_path)
                        pvr_exists = os.path.exists(full_pvr_path)

                        # debug statements for file existence
                        if self.debug: print(f"PVP exists: {pvp_exists}, PVR exists: {pvr_exists}")

                        apply_palette = True if (cur_file.lower().endswith(".pvp") and pvr_exists) or (
                                cur_file.lower().endswith(".pvr") and pvp_exists) else False

                        act_buffer = bytearray()

                        if pvp_exists:
                            self.load_pvp(full_pvp_path, act_buffer, full_pvp_path)

                        if pvr_exists:
                            self.load_pvr(full_pvr_path, apply_palette, act_buffer, os.path.basename(cur_file))

                if self.log and self.log_content != '':
                    with open(os.path.join(self.out_dir, 'pvr_log.txt'), 'w') as l:
                        l.write(self.log_content)

        def get_image_buffer(self):
            return self.image_buffer


        def read_col(self, px_format, color):

            if px_format == 0:  # ARGB1555
                a = ((color >> 15) & 0x1) * 0xff
                r = int(((color >> 10) & 0x1f) * 0xff / 0x1f)
                g = int(((color >> 5) & 0x1f) * 0xff / 0x1f)
                b = int((color & 0x1f) * 0xff / 0x1f)
                return (r, g, b, a)

            elif px_format == 1:  # RGB565
                a = 0xff
                r = int(((color >> 11) & 0x1f) * 0xff / 0x1f)
                g = int(((color >> 5) & 0x3f) * 0xff / 0x3f)
                b = int((color & 0x1f) * 0xff / 0x1f)
                return (r, g, b, a)

            elif px_format == 2:  # ARGB4444
                a = ((color >> 12) & 0xf) * 0x11
                r = ((color >> 8) & 0xf) * 0x11
                g = ((color >> 4) & 0xf) * 0x11
                b = (color & 0xf) * 0x11
                return (r, g, b, a)

            elif px_format == 5:  # RGB555
                a = 0xFF
                r = int(((color >> 10) & 0x1f) * 0xff / 0x1f)
                g = int(((color >> 5) & 0x1f) * 0xff / 0x1f)
                b = int((color & 0x1f) * 0xff / 0x1f)
                return (r, g, b, a)

            elif px_format in [7]:  # ARGB8888
                a = (color >> 24) & 0xFF
                r = (color >> 16) & 0xFF
                g = (color >> 8) & 0xFF
                b = color & 0xFF
                return (r, g, b, a)

            elif px_format in [14]:  # RGBA8888
                r = (color >> 24) & 0xFF
                g = (color >> 16) & 0xFF
                b = (color >> 8) & 0xFF
                a = color & 0xFF
                return (r, g, b, a)

            elif px_format == 3:

                # YUV422
                yuv0, yuv1 = color

                y0 = (yuv0 >> 8) & 0xFF
                u = yuv0 & 0xFF
                y1 = (yuv1 >> 8) & 0xFF
                v = yuv1 & 0xFF

                # YUV to RGB conversion
                c0 = y0 - 16
                c1 = y1 - 16
                d = u - 128
                e = v - 128

                r0 = max(0, min(255, int((298 * c0 + 409 * e + 128) >> 8)))
                g0 = max(0, min(255, int((298 * c0 - 100 * d - 208 * e + 128) >> 8)))
                b0 = max(0, min(255, int((298 * c0 + 516 * d + 128) >> 8)))

                r1 = max(0, min(255, int((298 * c1 + 409 * e + 128) >> 8)))
                g1 = max(0, min(255, int((298 * c1 - 100 * d - 208 * e + 128) >> 8)))
                b1 = max(0, min(255, int((298 * c1 + 516 * d + 128) >> 8)))

                return r0, g0, b0, r1, g1, b1

        def read_pal(self, mode, color, act_buffer):

            if mode == 4444:
                red = ((color >> 8) & 0xf) << 4
                green = ((color >> 4) & 0xf) << 4
                blue = (color & 0xf) << 4
                alpha = '-'

            if mode == 555:
                red = ((color >> 10) & 0x1f) << 3
                green = ((color >> 5) & 0x1f) << 3
                blue = (color & 0x1f) << 3
                alpha = '-'

            elif mode == 565:
                red = ((color >> 11) & 0x1f) << 3
                green = ((color >> 5) & 0x3f) << 2
                blue = (color & 0x1f) << 3
                alpha = '-'

            elif mode == 8888:
                blue = (color >> 0) & 0xFF
                green = (color >> 8) & 0xFF
                red = (color >> 16) & 0xFF
                alpha = (color >> 24) & 0xFF

            act_buffer += bytes([red, green, blue])
            return act_buffer

        def read_pvp(self, f, act_buffer):

            f.seek(0x08)
            pixel_type = int.from_bytes(f.read(1), 'little')
            if pixel_type == 1:
                mode = 565
            elif pixel_type == 2:
                mode = 4444
            elif pixel_type == 6:
                mode = 8888
            else:
                mode = 555

            f.seek(0x0e)
            ttl_entries = int.from_bytes(f.read(2), 'little')

            f.seek(0x10)  # start palette data
            current_offset = 0x10

            for counter in range(0, ttl_entries):
                if mode != 8888:
                    color = int.from_bytes(f.read(2), 'little')
                    act_buffer = self.read_pal(mode, color, act_buffer)
                    current_offset += 0x2
                else:
                    color = int.from_bytes(f.read(4), 'little')
                    act_buffer = self.read_pal(mode, color, act_buffer)
                    current_offset += 0x4

            return act_buffer, mode, ttl_entries

        def image_flip(self, data, w, h, cmode):

            if cmode == 'RGB':
                pixels_len = 3
            elif cmode == 'RGBA':
                pixels_len = 4
            else:
                pixels_len = 1

            if self.flip:
                data = (np.flipud((np.array(data)).reshape(h, w, -1)).flatten()).reshape(-1, pixels_len).tolist()

            return data


        def save_image(self, file_name, data, bits, w, h, cmode, palette):

            if not self.buffer_mode:
                os.makedirs(self.out_dir, exist_ok=True)

            if self.buffer_mode and self.buffer_pvr:
                self.image_buffer = self.PIL_buffer(file_name, data, bits, w, h, cmode, palette)
                return self.image_buffer

            elif self.fmt == 'png':
                self.save_png(file_name, data, bits, w, h, cmode, palette)
            elif self.fmt == 'bmp':
                self.save_bmp(file_name, data, bits, w, h, cmode, palette)
            elif self.fmt == 'tga':
                self.save_tga(file_name, data, bits, w, h, cmode, palette)

            if not self.silent: print(fr"{self.out_dir}\{file_name[:-4]}.{self.fmt} --> DONE!")

        def PIL_buffer(self, file_name, data, bits, w, h, cmode, palette=None):

            # convert data to PIL
            if 'PAL' in cmode:
                # palette-based images
                if cmode == 'RGB-PAL16':
                    # 4-bit palette (16 colors)
                    data = [item for sublist in data for item in sublist]
                    packed_data = bytearray()
                    for i in range(0, len(data), 2):
                        if i + 1 < len(data):
                            packed_data.append((data[i] << 4) | data[i + 1])
                        else:
                            packed_data.append(data[i] << 4)
                    data = packed_data
                else:
                    # 8-bit palette (256 colors)
                    data = bytes([item for sublist in data for item in sublist])

                # PIL image in 'P' mode
                img = Image.frombytes('P', (w, h), data)

                # palette to PIL format (list of RGB values)
                pil_palette = []
                for color in palette:
                    pil_palette.extend(color[:3])  # Take only RGB components

                img.putpalette(pil_palette)

            else:
                # direct color modes
                if cmode == 'RGB':
                    mode = 'RGB'
                    # convert to RGB bytes
                    pixel_data = bytearray()
                    for pixel in data:
                        pixel_data.extend([pixel[0], pixel[1], pixel[2]])
                    data = bytes(pixel_data)
                elif cmode == 'RGBA':
                    mode = 'RGBA'
                    # convert to RGBA bytes
                    pixel_data = bytearray()
                    for pixel in data:
                        pixel_data.extend([pixel[0], pixel[1], pixel[2], pixel[3]])
                    data = bytes(pixel_data)

                img = Image.frombytes(mode, (w, h), data)

            # CRC if logging is enabled
            if self.log:
                # image to bytes for CRC calculation
                if img.mode == 'P':
                    # use the raw data + palette
                    crc_data = img.tobytes() + bytes(img.palette.getdata()[1])
                else:
                    crc_data = img.tobytes()
                self.crc_value = hex(zlib.crc32(crc_data)).upper()[2:]

            return img

        # TGA does NOT support palettized images!
        def save_tga(self, file_name, data, bits, w, h, cmode, palette=None):
            # Define TGA header
            tga_header = bytearray([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, w & 255, (w >> 8) & 255,
                                    h & 255, (h >> 8) & 255, 32, 0])

            # TGA is not reversed by default
            pixel_data = bytearray()

            # append the pixel data
            for pixel in data:
                # BGRA format
                pixel_data.extend([pixel[2], pixel[1], pixel[0], pixel[3]])

            # combine the header and pixel data
            tga_data = tga_header + pixel_data

            if self.log:
                self.crc_value = hex(zlib.crc32(tga_data)).upper()[2:]

            # save the TGA file
            with open(fr'{self.out_dir}\{file_name[:-4]}.tga', "wb") as tga_file:
                tga_file.write(tga_data)

        def save_bmp(self, file_name, data, bits, w, h, cmode, palette=None):
            # BMP file header
            file_header = bytearray([66, 77, 54, 0, 0, 0, 0, 0, 0, 0, 54, 0, 0, 0])  # BMP string
            pixel_data = bytearray()

            # DIB header
            if cmode == 'RGB':
                bpp_var = 24
            elif cmode == 'RGBA':
                bpp_var = 32
            else:
                bpp_var = bits

            # print(len(palette))
            if 'PAL' in cmode:
                # palette to DIB header
                palette_data = bytearray()
                for color in palette:
                    palette_data.extend([color[2], color[1], color[0], 0])  # Assuming RGB format, add padding
            else:
                palette_data = bytes()
                palette = bytes(0)

            dib_header = bytearray([40, 0, 0, 0,  # DIB header size
                                    w & 255, (w >> 8) & 255, (w >> 16) & 255, (w >> 24) & 255,  # Image width
                                    h & 255, (h >> 8) & 255, (h >> 16) & 255, (h >> 24) & 255,  # Image height
                                    1, 0,  # color planes
                                    bpp_var, 0,  # bits per pixel
                                    0, 0, 0, 0,  # compression method (0 for uncompressed)
                                    0, 0, 0, 0,  # image size (0 for uncompressed)
                                    0, 0, 0, 0,  # horizontal resolution (pixels per meter)
                                    0, 0, 0, 0,  # vertical resolution (pixels per meter)
                                    len(palette) & 255, (len(palette) >> 8) & 255, 0, 0,
                                    # number of colors in the palette
                                    0, 0, 0, 0])  # number of important colors

            # combine the header and DIB header
            header = file_header + dib_header + palette_data

            if 'PAL' in cmode:
                data = [item for sublist in data for item in sublist]
                # calculate the length of each index sublist

                if cmode == 'RGB-PAL16':
                    sublist_length = w // 2
                else:
                    sublist_length = w  # 'RGB-PAL256'

                sublists = [data[i:i + sublist_length] for i in range(0, len(data), sublist_length)]
                reversed_sublists = sublists[::-1]
                pixel_data = bytes([item for sublist in reversed_sublists for item in sublist])

            else:
                # Bmp default order is left-right, bottom-top
                for y in range(h - 1, -1, -1):
                    for x in range(w):
                        # BGRA format
                        pixel = data[y * w + x]
                        if cmode == 'RGBA':
                            pixel_data.extend([pixel[2], pixel[1], pixel[0], pixel[3]])
                        elif cmode == 'RGB':
                            pixel_data.extend([pixel[2], pixel[1], pixel[0]])

            # combine the header, palette (if any), and pixel data
            bmp_data = header + pixel_data

            if self.log:
                self.crc_value = hex(zlib.crc32(bmp_data)).upper()[2:]

            # save the BMP file
            with open(fr'{self.out_dir}\{file_name[:-4]}.bmp', "wb") as bmp_file:
                bmp_file.write(bmp_data)


        def save_png(self, file_name, data, bits, w, h, cmode, palette):

            Pixel = None
            # print(cmode)

            if cmode == 'RGB':
                Pixel = tuple[int, int, int]

            elif cmode == 'RGBA':
                Pixel = tuple[int, int, int, int]

            def encode_data(image_data: list[list[Pixel]]) -> list[int]:
                ret = []

                for row in image_data:
                    ret.extend([0] + [pixel for color in row for pixel in color])

                return ret

            def calculate_checksum(chunk_type: bytes, data: bytes) -> int:
                checksum = zlib.crc32(chunk_type)
                checksum = zlib.crc32(data, checksum)
                return checksum

            def palette_to_bytearray(palette):
                # RGB tuple 3 components
                palette = [tuple(rgb[:3]) for rgb in palette]

                # RGB tuples packed into a bytearray
                byte_array = bytearray()
                for rgb in palette:
                    byte_array.extend(struct.pack('BBB', *rgb))
                return byte_array

            color_type = 2  # truecolor by default

            if cmode == 'RGB':
                color_type = 2  # truecolor
            elif cmode == 'RGBA':
                color_type = 6  # truecolor with alpha
            elif 'PAL' in cmode:
                color_type = 3  # indexed color

                # convert palette to a bytearray
                bytearray_palette = palette_to_bytearray(palette)

            if 'PAL' in cmode:
                # create indexes
                indexes = [item for sublist in data for item in sublist]
                image_bytes = bytearray([0] + indexes)  # filter type 0 for the first scanline

                png_array = []

                if cmode == 'RGB-PAL16':
                    row_lenght = (w // 2)
                else:
                    row_lenght = w

                for y in range(h):
                    png_array.append(0)  # filter type 0 for each scanline
                    for x in range(row_lenght):
                        png_array.append(x + y * row_lenght + 1)

                # rearrange indexes based on png_array order
                image_data = bytearray([image_bytes[i] for i in png_array])

            else:
                # arrange image data into rows
                image_data = bytearray(encode_data([data[i:i + w] for i in range(0, len(data), w)]))

            # compress image data using zlib with compression level 1, not too slow!
            compressed_data = zlib.compress(image_data, level=1)

            # write PNG signature
            png_data = b'\x89PNG\r\n\x1a\n'

            with open(fr'{self.out_dir}\{file_name[:-4]}.png', "wb") as out:

                # write IHDR chunk
                ihdr_chunk = struct.pack('!I', w) + struct.pack('!I', h) + bytes([bits, color_type, 0, 0, 0])
                checksum = calculate_checksum(b'IHDR', ihdr_chunk)
                png_data+=(struct.pack('!I', len(ihdr_chunk)) + b'IHDR' + ihdr_chunk + struct.pack('!I', checksum))

                if 'PAL' in cmode:
                    # write PLTE chunk
                    checksum = calculate_checksum(b'PLTE', bytearray_palette)
                    png_data+=(
                        struct.pack('!I', len(bytearray_palette)) + b'PLTE' + bytearray_palette + struct.pack('!I',
                                                                                                              checksum))

                # write IDAT chunk (compressed image data)
                checksum = calculate_checksum(b'IDAT', compressed_data)
                # print(struct.pack('!I', len(compressed_data)))
                png_data+=(
                    struct.pack('!I', len(compressed_data)) + b'IDAT' + compressed_data + struct.pack('!I', checksum))

                # write IEND chunk
                checksum = calculate_checksum(b'IEND', b'')
                png_data+=(struct.pack('!I', 0) + b'IEND' + struct.pack('!I', checksum))

                if self.log:
                    self.crc_value = hex(zlib.crc32(png_data)).upper()[2:]

                out.write(png_data)

        def write_act(self, act_buffer, file_name):

            base_dir = os.path.dirname(file_name)
            act_dir = os.path.join(base_dir, 'ACT')
            os.makedirs(act_dir, exist_ok=True)


            # create the full file path in the "ACT" folder
            file_path = os.path.join(act_dir, f"{os.path.basename(file_name)[:-4]}.ACT")

            # write to the file in binary mode
            with open(file_path, 'w+b') as n:

                # pad file with 0x00 if 16-color palette

                if len(act_buffer) < 768:
                    act_file = bytes(act_buffer) + bytes(b'\x00' * (768 - len(act_buffer)))
                else:
                    act_file = bytes(act_buffer)
                n.write(act_file)

        def decode_pvr(self, f, file_name, w, h, offset=None, px_format=None, tex_format=None, apply_palette=None,
                       act_buffer=None):
            f.seek(offset)
            data = bytearray()

            if tex_format not in [9, 10, 11, 12, 14, 15]:
                arr = Pypvr().twiddle(w, h)

            if tex_format in [5, 6, 7, 8]:

                cmode = None
                if tex_format in [7, 8]:  # 8bpp
                    palette_entries = 256
                    bits = 8
                    pixels = list(f.read(w * h))
                    data = [pixels[i] for i in arr]

                    if self.flip != '':
                        data = self.image_flip(data, w, h, cmode)
                        # flatten the nested list and convert each value to an integer
                        data = [int(value) for sublist in data for value in sublist]

                    # 4bpp, convert to 8bpp
                else:
                    palette_entries = 16
                    bits = 4
                    pixels = bytearray(f.read(w * h // 2))  # read only required amount of bytes

                    # read 4bpp to 8bpp indexes
                    data = []
                    for i in range(len(pixels)):
                        data.append(((pixels[i]) & 0x0f) * 0x11)  # last 4 bits
                        data.append((((pixels[i]) & 0xf0) >> 4) * 0x11)  # first 4 bits

                    # assuming 'data' contains the 8bpp indexes
                    new_pixels = bytearray(data)

                    # detwiddle 8bpp indexes
                    data = []
                    for num in arr:
                        data.append(new_pixels[num])

                    if self.flip != '':
                        data = self.image_flip(data, w, h, cmode)

                        # flatten the nested list and convert each value to an integer
                        data = [int(value) for sublist in data for value in sublist]

                    data = bytearray(data)  # 8bpp "twiddled data" back into "pixels" variable
                    # convert back to 4bpp indexes with swapped upper and lower bits

                    converted_data = bytearray()
                    for i in range(0, len(data), 2):
                        # swap the position of upper and lower bits
                        index1 = (data[i] // 0x11) << 4 | (data[i + 1] // 0x11)

                        # append the modified index to the converted data
                        converted_data.append(index1)

                    data = converted_data

                data = [data]

                if palette_entries == 16:

                    if apply_palette:
                        palette = [tuple(act_buffer[i:i + 3]) for i in range(0, len(act_buffer), 3)]

                    else:
                        palette = [(i * 17, i * 17, i * 17) for i in range(16)]
                    cmode = 'RGB-PAL16'

                elif palette_entries == 256:
                    if apply_palette:
                        palette = [tuple(act_buffer[i:i + 3]) for i in range(0, len(act_buffer), 3)]

                    else:
                        palette = [(i, i, i) for i in range(256)]
                    cmode = 'RGB-PAL256'

                if self.buffer_mode and self.buffer_pvr:
                    self.image_buffer = self.save_image(file_name, data, bits, w, h, cmode, palette)

                else:
                    self.save_image(file_name, data, bits, w, h, cmode, palette)

            # VQ
            elif tex_format in [3, 4, 16, 17]:

                codebook_size = 256

                # SmallVQ - Thanks Kion! :)

                if tex_format == 16:
                    if w <= 16:
                        codebook_size = 16
                    elif w == 32:
                        codebook_size = 32
                    elif w == 64:
                        codebook_size = 128
                    else:
                        codebook_size = 256

                # SmallVQ + Mips
                elif tex_format == 17:
                    if w <= 16:
                        codebook_size = 16
                    elif w == 32:
                        codebook_size = 64
                    else:
                        codebook_size = 256

                codebook = []

                # BUMP
                if px_format in [4]:
                    cmode = 'RGB'
                    for l in range(codebook_size):
                        block = []
                        for i in range(4):
                            pixel = (int.from_bytes(f.read(2), 'little'))
                            pix_col = self.bump_to_rgb(pixel)
                            block.append(pix_col)

                        codebook.append(block)

                # YUV422
                elif px_format in [3]:
                    cmode = 'RGB'
                    yuv_codebook = []
                    for l in range(codebook_size):
                        block = []
                        for i in range(4):
                            pixel = (int.from_bytes(f.read(2), 'little'))
                            block.append(pixel)

                        r0, g0, b0, r1, g1, b1 = self.read_col(px_format, (block[0], block[3]))
                        r2, g2, b2, r3, g3, b3 = self.read_col(px_format, (block[1], block[2]))

                        yuv_codebook.append([(r0, g0, b0), (r2, g2, b2), (r3, g3, b3), (r1, g1, b1)])

                    codebook = yuv_codebook

                else:
                    cmode = 'RGBA'
                    for l in range(codebook_size):
                        block = []
                        for i in range(4):
                            pixel = (int.from_bytes(f.read(2), 'little'))
                            pix_col = self.read_col(px_format, pixel)
                            block.append(pix_col)

                        codebook.append(block)

                # VQ Mips!
                if tex_format in [4, 17]:

                    pvr_dim = [4, 8, 16, 32, 64, 128, 256, 512, 1024]
                    mip_size = [0x10, 0x40, 0x100, 0x400, 0x1000, 0x4000, 0x10000, 0x40000]
                    size_adjust = {4: 1, 17: 1}  # 8bpp size is 4bpp *2
                    extra_mip = {4: 0x6, 17: 0x6, }  # smallest mips fixed size

                    for i in range(len(pvr_dim)):
                        if pvr_dim[i] == w:
                            mip_index = i - 1
                            break

                    # skip mips for image data offset
                    mip_sum = (sum(mip_size[:mip_index]) * size_adjust[tex_format]) + (extra_mip[tex_format])
                    f.seek(f.tell() + mip_sum)

                # read pixel_index:
                pixel_list = []
                bytes_to_read = int((w * h) / 4)

                # each index stores 4 pixels
                for i in range(bytes_to_read):
                    pixel_index = (int.from_bytes(f.read(1), 'little'))
                    pixel_list.append(int(pixel_index))

                # detwiddle image data indices, put them into arr list
                arr = Pypvr().twiddle(int(w / 2), int(h / 2))

                # create an empty 2D array to store pixel data
                image_array = [[(0, 0, 0, 0) for _ in range(w)] for _ in range(h)]

                # iterate over the blocks and update the pixel values in the array
                i = 0
                for y in range(h // 2):
                    for x in range(w // 2):
                        image_array[y * 2][x * 2] = codebook[pixel_list[arr[i]]][0]
                        image_array[y * 2 + 1][x * 2] = codebook[pixel_list[arr[i]]][1]
                        image_array[y * 2][x * 2 + 1] = codebook[pixel_list[arr[i]]][2]
                        image_array[y * 2 + 1][x * 2 + 1] = codebook[pixel_list[arr[i]]][3]
                        i += 1

                # flatten the 2D array to a 1D list for putdata
                data = [pixel for row in image_array for pixel in row]
                if self.flip != '':
                    data = self.image_flip(data, w, h, cmode)

                palette = ''
                # save the image
                self.save_image(file_name, data, 8, w, h, cmode, palette)

            # BMP ABGR8888
            elif tex_format in [14, 15]:
                pixels = [int.from_bytes(f.read(4), 'little') for _ in range(w * h)]
                data = [(self.read_col(14, p)) for p in pixels]

                palette = ''
                cmode = 'RGBA'

                if self.flip != '':
                    data = self.image_flip(data, w, h, cmode)

                # save the image
                self.save_image(file_name, data, 8, w, h, cmode, palette)

            # BUMP loop
            elif px_format == 4:
                pixels = [int.from_bytes(f.read(2), 'little') for _ in range(w * h)]
                data = [self.bump_to_rgb(p) for p in (pixels[i] for i in arr)]

                palette = ''
                cmode = 'RGB'

                if self.flip != '':
                    data = self.image_flip(data, w, h, cmode)

                # save the image
                self.save_image(file_name, data, 8, w, h, cmode, palette)

            # ARGB modes
            elif px_format in [0, 1, 2, 5, 7, 18]:

                pixels = [int.from_bytes(f.read(2), 'little') for _ in range(w * h)]

                if tex_format not in [9, 10, 11, 12, 14, 15]:  # If Twiddled
                    data = [(self.read_col(px_format, p)) for p in (pixels[i] for i in arr)]
                else:
                    data = [(self.read_col(px_format, p)) for p in pixels]

                palette = ''
                cmode = 'RGBA'

                if self.flip != '':
                    data = self.image_flip(data, w, h, cmode)

                # save the image
                self.save_image(file_name, data, 8, w, h, cmode, palette)

            # YUV420 modes
            elif px_format in [6]:
                data = []
                self.yuv420_to_rgb(f, w, h, data)

                palette = ''
                cmode = 'RGB'

                if self.flip != '':
                    data = self.image_flip(data, w, h, cmode)

                # save the image
                self.save_image(file_name, data, 8, w, h, cmode, palette)

            # YUV422 modes
            elif px_format in [3]:
                data = []

                # twiddled
                if tex_format not in [9, 10, 11, 12, 14, 15]:
                    i = 0
                    offset = f.tell()

                    for y in range(h):
                        for x in range(0, w, 2):
                            f.seek(offset + (arr[i] * 2))
                            yuv0 = int.from_bytes(f.read(2), 'little')
                            i += 1
                            f.seek(offset + (arr[i] * 2))
                            yuv1 = int.from_bytes(f.read(2), 'little')
                            r0, g0, b0, r1, g1, b1 = self.read_col(px_format, (yuv0, yuv1))
                            data.append((r0, g0, b0))
                            data.append((r1, g1, b1))
                            i += 1

                else:
                    for y in range(h):
                        for x in range(0, w, 2):
                            # read yuv0 and yuv1 separately
                            yuv0 = int.from_bytes(f.read(2), 'little')
                            yuv1 = int.from_bytes(f.read(2), 'little')
                            r0, g0, b0, r1, g1, b1 = self.read_col(px_format, (yuv0, yuv1))
                            data.append((r0, g0, b0))
                            data.append((r1, g1, b1))

                palette = ''
                cmode = 'RGB'

                if self.flip != '':
                    data = self.image_flip(data, w, h, cmode)

                # save the image
                self.save_image(file_name, data, 8, w, h, cmode, palette)


        def load_pvr(self, PVR_file, apply_palette, act_buffer, file_name,buffer_pvr=None):
            px_modes = Pypvr().px_modes
            tex_modes = Pypvr().tex_modes

            try:
                if buffer_pvr:
                    f_buffer = io.BytesIO(buffer_pvr)
                else:
                    with open(PVR_file, 'rb') as f:
                        f_buffer = io.BytesIO(f.read())

                header_data = f_buffer.getvalue()
                gbix_offset = header_data.find(b"GBIX")

                if gbix_offset != -1:
                    f_buffer.seek(gbix_offset + 0x4)
                    gbix_size = int.from_bytes(f_buffer.read(4), byteorder='little')
                    if gbix_size == 0x8:
                        gbix_val1 = int.from_bytes(f_buffer.read(4), byteorder='little')
                        gbix_val2 = int.from_bytes(f_buffer.read(4), byteorder='little')
                        if self.debug:
                            print(hex(gbix_val1), hex(gbix_val2))
                    elif gbix_size == 0x4:
                        gbix_val1 = int.from_bytes(f_buffer.read(4), byteorder='little')
                        gbix_val2 = ''
                    else:
                        print('invalid or unsupported GBIX size:', gbix_size, file_name)
                else:
                    if self.debug:
                        print('GBIX found at:', hex(gbix_offset)) if gbix_offset != -1 else print('GBIX not found')

                    gbix_val1 = ''
                    gbix_val2 = ''


                offset = header_data.find(b"PVRT")
                if offset != -1 or len(header_data) < 0x10:
                    f_buffer.seek(offset + 0x8)

                    # pixel format
                    px_format = int.from_bytes(f_buffer.read(1), byteorder='little')
                    tex_format = int.from_bytes(f_buffer.read(1), byteorder='little')

                    f_buffer.seek(f_buffer.tell() + 2)

                    # image size
                    w = int.from_bytes(f_buffer.read(2), byteorder='little')
                    h = int.from_bytes(f_buffer.read(2), byteorder='little')
                    offset = f_buffer.tell()

                    if self.debug:
                        print(PVR_file.split('/')[-1], 'size:', w, 'x', h, 'format:',
                              f'[{tex_format}] {tex_modes[tex_format]}', f'[{px_format}] {px_modes[px_format]}')

                    if tex_format in [2, 4, 6, 8, 10, 12, 15, 17, 18]:
                        if tex_format in [2, 6, 8, 10, 15, 18]:
                            # Mips skip
                            pvr_dim = [4, 8, 16, 32, 64, 128, 256, 512, 1024]
                            mip_size = [0x20, 0x80, 0x200, 0x800, 0x2000, 0x8000, 0x20000, 0x80000]
                            size_adjust = {2: 4, 6: 1, 8: 2, 10: 4, 15: 8, 18: 4}  # 8bpp size is 4bpp *2
                            extra_mip = {2: 0x2c, 6: 0xc, 8: 0x18, 10: 0x2c, 15: 0x54,
                                         18: 0x30}  # smallest mips fixed size

                            for i in range(len(pvr_dim)):
                                if pvr_dim[i] == w:
                                    mip_index = i - 1
                                    break

                            mip_sum = (sum(mip_size[:mip_index]) * size_adjust[tex_format]) + (
                                extra_mip[tex_format])

                            offset += mip_sum

                    self.decode_pvr(f_buffer, file_name, w, h, offset, px_format, tex_format, apply_palette,
                                    act_buffer)

                    # LOG stuff for later reimport
                    if self.log:
                        self.log_content += (
                            f"IMAGE FILE : {os.path.normpath(os.path.join(self.out_dir, file_name))[:-4]}.{self.fmt}\n"
                            f"TARGET DIR : {os.path.normpath(os.path.dirname(PVR_file))}\n"
                            f"ENC PARAMS : {' '.join(f'-{mode}' for mode in tex_modes[tex_format].split())}"
                            f" -{px_modes[px_format]}"
                            f"{' -flip' if self.flip else ''}"
                            f"{' -nopvp' if self.nopvp else ''}"
                            f"{f' -gi {gbix_val1}' if gbix_val1 else ''}"
                            f"{f' -gitrim' if not gbix_val2 and gbix_val1 else ''}"
                            f" \nIMAGE SIZE : {w}x{h}\nDATA CRC32 : {self.crc_value}\n"
                            f"---------------\n"
                        )

                else:
                    print(f"{self.out_dir}\\{PVR_file} --> ERROR!  PVRT header not found!")

            except Exception:
                if not self.image_buffer: print(f'{self.out_dir}\\{PVR_file} --> ERROR!  ')

        def load_pvp(self, PVP_file, act_buffer, file_name,pvp_buffer = None):

            try:

                if pvp_buffer:
                    f_buffer = io.BytesIO(pvp_buffer)
                else:
                    with open(PVP_file, 'rb') as f:
                        f_buffer = io.BytesIO(f.read())

                file_size = len(f_buffer.read())
                f_buffer.seek(0x0)
                PVP_check = f_buffer.read(4)

                if PVP_check == b'PVPL' and file_size > 0x10:  # PVPL header and size are OK!
                        act_buffer, mode, ttl_entries = self.read_pvp(f_buffer, act_buffer)
                        if not pvp_buffer and self.act_export:self.write_act(act_buffer, file_name)
                else:
                    print('Invalid .PVP file!')  # skip this file

            except:
                print(f'PVP data error! {PVP_file}')
            return act_buffer




        def bump_to_rgb(self, SR_value):
            # process SR value
            S = (1.0 - ((SR_value >> 8) / 255.0)) * math.pi / 2
            R = (SR_value & 0xFF) / 255.0 * 2 * math.pi - 2 * math.pi * (SR_value & 0xFF > math.pi)
            red = (math.sin(S) * math.cos(R) + 1.0) * 0.5
            green = (math.sin(S) * math.sin(R) + 1.0) * 0.5
            blue = (math.cos(S) + 1.0) * 0.5

            # convert to RGB values
            return (
                int(red * 255),
                int(green * 255),
                int(blue * 255)
            )

        def yuv420_to_rgb(self, f, w, h, data):
            # precompute conversion coefficients
            u_offset = -128
            v_offset = -128
            r_factor = 1.402
            g_u_factor = -0.344136
            g_v_factor = -0.714136
            b_factor = 1.772

            # initialize RGB buffer
            rgb_data = np.zeros((h, w, 3), dtype=np.uint8)

            # calculate the number of macroblocks
            mb_width = w // 16
            mb_height = h // 16

            # loop over each macroblock (16x16 pixels)
            for mb_y in range(mb_height):
                for mb_x in range(mb_width):
                    # read U and V data for the 16x16 block (8x8 U and V values)
                    u_block = np.frombuffer(f.read(64), dtype=np.uint8).reshape((8, 8))
                    v_block = np.frombuffer(f.read(64), dtype=np.uint8).reshape((8, 8))

                    # read Y data for the four 8x8 blocks (Y0, Y1, Y2, Y3)
                    y_blocks = [np.frombuffer(f.read(64), dtype=np.uint8).reshape((8, 8)) for _ in range(4)]

                    # upscale U and V to 16x16 to match the 16x16 Y blocks using np.kron (faster than np.repeat)
                    u_block = np.kron(u_block, np.ones((2, 2), dtype=np.uint8))
                    v_block = np.kron(v_block, np.ones((2, 2), dtype=np.uint8))

                    # prepare Y data for the full 16x16 block
                    full_y = np.zeros((16, 16), dtype=np.uint8)
                    full_y[:8, :8] = y_blocks[0]
                    full_y[:8, 8:] = y_blocks[1]
                    full_y[8:, :8] = y_blocks[2]
                    full_y[8:, 8:] = y_blocks[3]

                    # convert U, V, and Y to RGB in a vectorized manner
                    u_block = u_block + u_offset
                    v_block = v_block + v_offset
                    r = np.clip(full_y + r_factor * v_block, 0, 255).astype(np.uint8)
                    g = np.clip(full_y + g_u_factor * u_block + g_v_factor * v_block, 0, 255).astype(np.uint8)
                    b = np.clip(full_y + b_factor * u_block, 0, 255).astype(np.uint8)

                    # assign RGB values to the final RGB buffer
                    rgb_data[mb_y * 16:(mb_y + 1) * 16, mb_x * 16:(mb_x + 1) * 16, 0] = r
                    rgb_data[mb_y * 16:(mb_y + 1) * 16, mb_x * 16:(mb_x + 1) * 16, 1] = g
                    rgb_data[mb_y * 16:(mb_y + 1) * 16, mb_x * 16:(mb_x + 1) * 16, 2] = b

            # convert rgb_data to a list of RGB tuples
            data.extend(tuple(rgb_data[y, x]) for y in range(h) for x in range(w))

            return data

    class Encode:

        def __init__(self, args_str=None,buffer_image = None):
            # default settings
            self.debug = False
            self.image_path = None
            self.out_dir = None
            self.tex_mode = None
            self.px_mode = None
            self.mm = False
            self.gbix = None
            self.gitrim = False
            self.pvpbank = None
            self.pvptrim = False
            self.flip = None
            self.vq_iter = None
            self.vq_rseed = None
            self.cla = None
            self.square_size = False
            self.rectangle_size = False
            self.stride_size = False
            self.yuv420_size = False
            self.silent = False
            self.nopvp = False
            self.vqalgo = None

            self.buffer_mode = False
            self.buffer_pvr = bytearray()
            self.buffer_pvp = bytearray()
            self.nearest = False
            self.buffer_image = buffer_image


            # supported image file extensions
            supported_images = ('.png', '.bmp', '.tga', '.gif', '.tif', '.jpg')

            # px_modes and tex_modes sets
            px_modes_args = {
                '1555', '565', '4444', 'yuv422', 'bump', '555', 'yuv420', '8888', 'p4bpp', 'p8bpp'
            }

            tex_modes_args = {
                'tw', 'twre', 'vq', 'pal4', 'pal8', 're', 'st', 'bmp', 'svq', 'twal'
            }

            if args_str:
                # extract image path
                image_pattern = r'([^\s]+(?:\s+[^\s]+)*\.(?:png|bmp|tga|gif|tif|jpg))'
                image_match = re.search(image_pattern, args_str, re.IGNORECASE)
                if image_match:
                    self.image_path = image_match.group(0).strip()

                # extract output directory (-o) with provided pattern
                out_dir_pattern = r'-o\s+([^\-]+(?:\s+[^\-]+)*)'
                out_dir_match = re.search(out_dir_pattern, args_str)
                if out_dir_match:
                    self.out_dir = out_dir_match.group(1).strip()
                    if not os.path.isabs(self.out_dir):
                        self.out_dir = os.path.abspath(self.out_dir)

                else:
                    self.out_dir = ''

                # regex to capture multi-word values and flags
                arg_pattern = r'-(\w+)(?:\s+([^\s-]+(?:\s+[^\s-]+)*))?'
                matches = re.finditer(arg_pattern, args_str)

                for match in matches:
                    flag = match.group(1).lower()
                    value = match.group(2)

                    if flag in tex_modes_args:
                        self.tex_mode = flag

                    elif flag in px_modes_args:
                        self.px_mode = flag

                    elif flag == 'mm':
                        self.mm = True

                    elif flag == 'gi' and value:
                        self.gbix = int(value)

                    elif flag == 'gitrim':
                        self.gitrim = True

                    elif flag == 'pvpbank' and value:
                        self.pvpbank = int(value)

                    elif flag == 'pvptrim':
                        self.pvptrim = True

                    elif flag == 'flip' and value:
                        self.flip = value

                    elif flag == 'vqi' and value:
                        self.vq_iter = int(value)

                    elif flag == 'vqa1':
                        self.vqalgo = 'vqa1'

                    elif flag == 'vqa2':
                        self.vqalgo = 'vqa2'

                    elif flag == 'vqs' and value:
                        if value == 'rand':
                            self.vq_rseed = value
                        else:
                            self.vq_rseed = int(value)

                    elif flag == 'cla':
                        self.cla = True

                    elif flag == 'dbg':
                        self.debug = True

                    elif flag == 'silent':
                        self.silent = True

                    elif flag == 'buffer':
                        self.buffer_mode = True

                    elif flag == 'nopvp':
                        self.nopvp = True

                    elif flag == 'near':
                        self.nearest = True


                # set defaults:
                if self.vq_rseed == None:
                    self.vq_rseed = 2

                elif self.vq_rseed == 'rand':
                    self.vq_rseed = None

                if self.vq_iter is None:
                    self.vq_iter = 10

                if self.pvpbank is None:
                    self.pvpbank = 0

                try:
                    # ensure the image_path is valid and supported
                    if not self.buffer_mode:
                        if not self.image_path or not self.image_path.lower().endswith(supported_images):
                            raise ValueError("Invalid or unsupported image file format.")

                    elif self.buffer_mode and self.buffer_image:
                        self.image_path = ''

                    else:
                        if not self.image_path or not self.image_path.lower().endswith(supported_images):
                            raise ValueError("Invalid or unsupported image file format.")

                    # 32 bpp BMP with ALPHA channel support for PIL
                    if self.image_path.lower().endswith('bmp'):
                        with open(self.image_path, 'rb') as b:
                            b.seek(14)
                            _, w, h, _, bpp, _, _, _, _, _, _ = struct.unpack('<IIIHHIIIIII', b.read(40))
                            if bpp == 32:
                                b.seek(54)
                                row_size = (w * 4 + 3) & ~3
                                pixel_array = []
                                for _ in range(h):
                                    row = list(struct.iter_unpack('BBBB', b.read(w * 4)))
                                    pixel_array.append([(r, g, b, a) for b, g, r, a in row])  # Convert BGRA to RGBA
                                    b.read(row_size - (w * 4))  # Skip padding if any
                                image = Image.fromarray(np.array(pixel_array[::-1], dtype=np.uint8),
                                                        'RGBA')  # Reverse rows
                            else:
                                image = Image.open(self.image_path)
                                w, h = image.size
                    else:
                        image = (Image.open(self.image_path) if not self.buffer_image else self.buffer_image)
                        w, h = image.size


                    image_mode = image.mode
                    unique_colors = image.getcolors(maxcolors=6500000)

                    self.img_size_check(w, h)

                    if self.debug:
                        print('Can be square:', self.square_size)
                        print('Can be rectangle:', self.rectangle_size)
                        print('Can be stride:', self.stride_size)
                        print('Can be YUV420:', self.yuv420_size)

                    # -------------------
                    # INVALID MODES CHECK
                    # -------------------

                    # check for invalid image sizes
                    if not any([self.square_size, self.rectangle_size, self.stride_size, self.yuv420_size]):
                        print(
                            'Invalid image size! Must be power of 2, multiple of 32 for stride, or multiple of 16 for yuv420!')
                        return

                    if w > 1024 or h > 1024:
                        print('Invalid image size! Height or Width cannot be over 1024 pixels!')
                        return

                    valid_combo = self.check_combination(self.tex_mode, self.px_mode)

                    # auto or empty tex_mode / px_mode
                    if self.tex_mode is None or self.px_mode is None:
                        self.auto_format(image, image_mode, unique_colors)
                    elif valid_combo == False:
                        print(f'Error! Invalid combination: -{self.tex_mode} -{self.px_mode}, trying auto')
                        self.tex_mode = None
                        self.px_mode = None
                        self.auto_format(image, image_mode, unique_colors)

                    # handle stride format with y420 mode
                    if self.stride_size and not any([self.square_size, self.rectangle_size]):
                        if self.px_mode == 'yuv420' and self.yuv420_size and self.tex_mode != 're':
                            self.tex_mode = 'st'
                            self.auto_format(image, image_mode, unique_colors)

                    # handle px_mode '555' (PCX converter only)
                    if self.px_mode == '555':
                        print('555 is for PCX converter only, using 1555!')
                        self.px_mode = '1555'

                    # exclude invalid palette modes
                    if 'pal' in self.tex_mode and self.px_mode not in ['1555', '4444', '565', '8888', 'p4bpp', 'p8bpp']:
                        if self.px_mode in ['p4bpp', 'p8bpp']:
                            print('Warning, placeholder pixel format!')
                        else:
                            print('Invalid color format, using 1555!')
                            self.px_mode = '1555'

                    # handle 'vq' and 'svq' modes for square textures
                    if any(mode in self.tex_mode for mode in ['vq', 'svq']):
                        if self.square_size:
                            if self.px_mode not in ['1555', '565', '4444', 'yuv422', 'bump']:
                                print(f'Error: "-{self.px_mode} -{self.tex_mode}" invalid color / type format!')
                                self.auto_format(image, image_mode, unique_colors)
                        else:
                            print('Cannot use VQ on non-square textures!')
                            self.tex_mode = None
                            self.auto_format(image, image_mode, unique_colors)

                        if 'svq' in self.tex_mode and h not in {8, 16, 32, 64}:
                            self.tex_mode = 'vq'
                            print('SmallVQ image height cannot be > 64, using VQ!')


                    if 'bmp' in self.tex_mode and self.square_size:
                        self.px_mode = '8888'
                        print('WARNING! Bitmap reserved format!')
                    elif 'bmp' in self.tex_mode and not self.square_size:
                        print('Error! Bitmap reserved format must be square!')
                        self.tex_mode = None
                        self.px_mode = None
                        self.auto_format(image, image_mode, unique_colors)
                        print(f'AUTO Mode: Using "-{self.px_mode} -{self.tex_mode}"')
                    elif self.px_mode == '8888' and 'pal' not in self.tex_mode:
                        if self.square_size:
                            self.tex_mode = 'bmp'
                            print('WARNING! Bitmap reserved format!')
                        else:
                            print(f'Error: "-{self.px_mode} -{self.tex_mode}" invalid color / type format!')
                            self.tex_mode = None
                            self.px_mode = None
                            self.auto_format(image, image_mode, unique_colors)
                            print(f'AUTO Mode: Using "-{self.px_mode} -{self.tex_mode}"')

                    # handle 'y420' mode, ensure it is compatible with 're' mode
                    if 'yuv420' in self.px_mode:
                        if self.tex_mode != 're':
                            if self.yuv420_size and not any([self.square_size, self.stride_size, self.rectangle_size]):
                                self.tex_mode = 're'
                            else:
                                self.px_mode = 'yuv422'
                            print(f'AUTO Mode: Using "-{self.px_mode} -{self.tex_mode}"')

                    # handle 'st' (stride) mode
                    if 'st' in self.tex_mode:
                        if not self.stride_size:
                            print(f"Image dimension Error: Can't Stride {w}x{h}")
                            self.tex_mode = None
                            self.auto_format(image, image_mode, unique_colors)
                            print(f'AUTO Mode: Using "-{self.px_mode} -{self.tex_mode}"')
                        else:
                            print('WARNING! Using stride format, bad performance, no mips!')

                    # special warnings

                    if 'yuv420' in self.px_mode:
                        print("WARNING! YUV420 mode!")

                    # handle mipmaps
                    if self.debug:
                        print('mips:', self.mm)

                    if self.mm and 'mm' not in self.tex_mode:
                        if self.square_size and self.tex_mode not in ['st', 'twre', 'yuv420']:
                            self.tex_mode += ' mm'
                        else:
                            print(f"Can't use mipmaps on non-square textures! ( {self.image_path}, {w}x{h} )")

                    # unused RGB alpha clean
                    if self.cla == True:
                        image = self.clean_alpha(image, w, h)

                    if self.debug:
                        print(f"Loading image: {self.image_path}")
                        print(f"Output Directory: {self.out_dir}")
                        print(f"Texture Mode: {self.tex_mode}")
                        print(f"Pixel Mode: {self.px_mode}")
                        print(f"GBIX: {self.gbix}")
                        print(f"GBTrim: {self.gitrim}")
                        print(f"PVPBank: {self.pvpbank}")
                        print(f"PVPTrim: {self.pvptrim}")
                        print(f"Flip: {self.flip}")
                        print(f"VQ Algo: {self.vqalgo}")
                        print(f"VQ Iteration: {self.vq_iter}")
                        print(f"VQ Random Seed: {self.vq_rseed}")
                        print(f"Clean Alpha: {self.cla}")
                        print(f"Nearest Resize: {self.nearest}")

                    self.load_image(image, self.image_path, self.flip, self.tex_mode, self.px_mode, self.gbix,
                                    self.gitrim,
                                    self.pvptrim, self.pvpbank, self.vq_iter, self.vq_rseed,
                                    self.out_dir,colors = None)

                except Exception as e:
                    print(f"An error occurred: {e}")

        def check_combination(self, tex_mode, px_mode):

            px_modes_list = ['1555', '565', '4444', 'yuv422', 'bump', '555', 'yuv420', '8888', 'p4bpp', 'p8bpp']
            tex_modes_list = ['tw', 'twre', 'vq', 'pal4', 'pal8', 're', 'st', 'bmp', 'svq', 'twal']

            # 1 = valid, 0 = invalid
            matrix = [
                # 0:1555, 1:565, 2:4444, 3:yuv422,4:bump', 5:555', 6:yuv420, 7:8888, 8:p4bpp, 9:p8bpp
                # 0  1  2  3  4  5  6  7  8  9
                [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],  # tw (Twiddled)
                [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],  # twre (Twiddled Rectangle)
                [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],  # vq (VQ)
                [1, 1, 1, 0, 0, 0, 0, 1, 1, 0],  # pal4 (Palette 4)
                [1, 1, 1, 0, 0, 0, 0, 1, 0, 1],  # pal8 (Palette 8)
                [1, 1, 1, 1, 0, 0, 1, 0, 0, 0],  # re (Rectangle)
                [1, 1, 1, 1, 0, 0, 0, 0, 0, 0],  # st (Stride)
                [0, 0, 0, 0, 0, 0, 0, 1, 0, 0],  # bmp (Bitmap)
                [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],  # svq (SmallVQ)
                [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],  # twal (Twiddled Alias Mips)
            ]

            # ensure that the input tex_mode and px_mode exist in the predefined sets
            if tex_mode not in tex_modes_list:
                return False
            if px_mode not in px_modes_list:
                return False

            # find the index of the texture and pixel modes
            tex_index = tex_modes_list.index(tex_mode)
            px_index = px_modes_list.index(px_mode)

            # check the matrix value (treat only 1 as valid)
            result = matrix[tex_index][px_index]

            if result == 1:
                return True
            else:
                return False

        def auto_format(self, image, image_mode, unique_colors):

            # auto-determines texture mode and pixel mode based on source image


            # check if only YUV420 mode is available
            if not self.square_size and not self.rectangle_size and not self.stride_size:
                if self.yuv420_size:
                    self.tex_mode, self.px_mode = 're', 'yuv420'
                else:
                    print('No conversion available for this image size!')
                return

            # if tex_mode or px_mode is already set, no need to auto-determine
            if self.tex_mode is not None and self.px_mode is not None:
                return

            if self.debug:
                print('Auto Mode')
                print(f"Source Image mode: {image_mode}")
                print(f"Number of unique colors: {len(unique_colors)}")

            # auto-determine the px_mode if not already set
            if self.px_mode is None:
                if image_mode == 'RGBA':
                    alpha = image.getchannel('A')
                    min_alpha, max_alpha = alpha.getextrema()
                    alpha_values = set(alpha.getdata())

                    if min_alpha < 255:
                        if min_alpha == 0 and max_alpha == 255 and alpha_values == {0, 255}:
                            self.px_mode = '1555'
                        else:
                            self.px_mode = '4444'
                    else:
                        self.px_mode = '565'
                else:
                    self.px_mode = '565'

                # special case for YUV420
                if self.yuv420_size and not (self.square_size or self.rectangle_size or self.stride_size):
                    self.px_mode = 'yuv420'

            # auto-determine the tex_mode if not already set
            if self.tex_mode is None:
                if self.stride_size and not (self.square_size or self.rectangle_size):
                    self.tex_mode = 'st'
                elif self.square_size or self.rectangle_size:
                    if self.px_mode in ['1555', '4444', '565', '8888', 'p4bpp', 'p8bpp']:
                        self.tex_mode = 'tw' if self.square_size else 'twre'
                        if image_mode == 'P':
                            self.tex_mode = 'pal8' if len(unique_colors) > 16 else 'pal4'
                    else:
                        self.tex_mode = 'tw' if self.square_size else 'twre'
                elif self.yuv420_size and not (self.square_size or self.rectangle_size):
                    if self.stride_size and self.px_mode != 're':
                        self.tex_mode = 'st'

            if 'vq' in self.tex_mode or 'svq' in self.tex_mode:
                if image_mode == 'RGBA' and self.cla == None:
                    self.cla = True


        def img_size_check(self, w, h):

            def is_powerof2(n):
                return n > 0 and (n & (n - 1)) == 0

            def is_square(width, height):
                return is_powerof2(width) and is_powerof2(height) and width == height

            def is_rectangle(width, height):
                return is_powerof2(width) and is_powerof2(height) and (width != height)

            def is_stride(width, height):
                # check if width is a multiple of 32 and between 32 and 992
                return (width % 32 == 0 and 32 <= width <= 992) and not is_powerof2(height)

            def is_yuv420(width, height):
                return width % 16 == 0 and height % 16 == 0

            if is_square(w, h):
                self.square_size = True
            if is_rectangle(w, h):
                self.rectangle_size = True
            if is_stride(w, h):
                self.stride_size = True
            if is_yuv420(w, h):
                self.yuv420_size = True

        # conversion methods
        def rgb_to_rgb565(self, rgb):
            r = (rgb[:, 0] >> 3).astype(np.uint16)
            g = (rgb[:, 1] >> 2).astype(np.uint16)
            b = (rgb[:, 2] >> 3).astype(np.uint16)
            return (r << 11) | (g << 5) | b

        def rgb_to_rgb555(self, rgb):
            r = (rgb[:, 0] >> 3).astype(np.uint16)
            g = (rgb[:, 1] >> 3).astype(np.uint16)
            b = (rgb[:, 2] >> 3).astype(np.uint16)
            return (r << 10) | (g << 5) | b

        def rgba_to_rgba4444(self, rgba):
            r = (rgba[:, 0] >> 4).astype(np.uint16)
            g = (rgba[:, 1] >> 4).astype(np.uint16)
            b = (rgba[:, 2] >> 4).astype(np.uint16)
            a = (rgba[:, 3] >> 4).astype(np.uint16)
            return (a << 12) | (r << 8) | (g << 4) | b

        def rgba_to_rgba1555(self, rgba):
            r = (rgba[:, 0] >> 3).astype(np.uint16)
            g = (rgba[:, 1] >> 3).astype(np.uint16)
            b = (rgba[:, 2] >> 3).astype(np.uint16)
            a = (rgba[:, 3] >> 7).astype(np.uint16)  # 1 bit for alpha
            return (a << 15) | (r << 10) | (g << 5) | b

        def rgb_to_yuv422(self, rgb):
            r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
            Y = np.clip((0.299 * r + 0.587 * g + 0.114 * b).astype(np.int32), 0, 255)
            U = np.clip((-0.169 * r - 0.331 * g + 0.499 * b + 128).astype(np.int32), 0, 255)
            V = np.clip((0.499 * r - 0.418 * g - 0.0813 * b + 128).astype(np.int32), 0, 255)
            return Y, U, V  # return Y, U, V separately

        def rgba_to_rgba8888(self, rgba):
            r = (rgba[:, 0]).astype(np.uint32)
            g = (rgba[:, 1]).astype(np.uint32)
            b = (rgba[:, 2]).astype(np.uint32)
            a = (rgba[:, 3]).astype(np.uint32)
            return (r << 24) | (g << 16) | (b << 8) | a

        def rgb_to_sr(self, rgb):
            red = rgb[..., 0] / 255.0
            green = rgb[..., 1] / 255.0
            blue = rgb[..., 2] / 255.0
            S = np.arccos(2 * blue - 1)
            R = np.arctan2(green - 0.5, red - 0.5)
            R = (R + np.pi / 16) % (2 * np.pi)  # flip the angle horizontally
            S = np.clip((1.0 - S / (np.pi / 2)) * 255, 0, 255).astype(np.uint16)
            R = np.clip((R / (2 * np.pi)) * 255, 0, 255).astype(np.uint16)
            SR_value = (S << 8) | R
            return SR_value

        def encode_yuv422(self, rgb_array, num_channels, px_size):
            reshaped_rgb_array = rgb_array.reshape(-1, 2, num_channels)
            Y, U, V = self.rgb_to_yuv422(reshaped_rgb_array.reshape(-1, num_channels))

            Y = Y.reshape(-1, 2)
            U = U.reshape(-1, 2)[:, 0]
            V = V.reshape(-1, 2)[:, 0]

            yuv422_values = np.zeros((Y.size + Y.size) // 2, dtype=px_size)
            yuv422_values[::2] = (Y[:, 0] << 8) | U
            yuv422_values[1::2] = (Y[:, 1] << 8) | V

            return yuv422_values

        def encode_yuv420(self, img_width, img_height, rgb_array):
            rgb_array = rgb_array.reshape((img_height, img_width, 3))

            r = rgb_array[:, :, 0].astype(np.float32)
            g = rgb_array[:, :, 1].astype(np.float32)
            b = rgb_array[:, :, 2].astype(np.float32)

            y_plane = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.uint8)
            u_plane_full = (-0.14713 * r - 0.28886 * g + 0.436 * b + 128).astype(np.int32)
            v_plane_full = (0.615 * r - 0.51499 * g - 0.10001 * b + 128).astype(np.int32)

            # perform downsampling by averaging 2x2 blocks
            u_plane = u_plane_full[::2, ::2] + u_plane_full[1::2, ::2] + u_plane_full[::2, 1::2] + u_plane_full[1::2,
                                                                                                   1::2]
            v_plane = v_plane_full[::2, ::2] + v_plane_full[1::2, ::2] + v_plane_full[::2, 1::2] + v_plane_full[1::2,
                                                                                                   1::2]
            u_plane = np.clip(u_plane // 4, 0, 255).astype(np.uint8)
            v_plane = np.clip(v_plane // 4, 0, 255).astype(np.uint8)

            # prepare YUV data array
            yuv_data = np.empty((img_height * img_width * 3) // 2, dtype=np.uint8)

            index = 0

            # write YUV data to the array
            for mb_y in range(0, img_height, 16):
                for mb_x in range(0, img_width, 16):
                    u_block = u_plane[mb_y // 2:mb_y // 2 + 8, mb_x // 2:mb_x // 2 + 8]
                    v_block = v_plane[mb_y // 2:mb_y // 2 + 8, mb_x // 2:mb_x // 2 + 8]

                    yuv_data[index:index + u_block.size] = u_block.ravel()
                    index += u_block.size
                    yuv_data[index:index + v_block.size] = v_block.ravel()
                    index += v_block.size

                    # write Y data for the four 8x8 blocks
                    y0_block = y_plane[mb_y:mb_y + 8, mb_x:mb_x + 8]
                    y1_block = y_plane[mb_y:mb_y + 8, mb_x + 8:mb_x + 16]
                    y2_block = y_plane[mb_y + 8:mb_y + 16, mb_x:mb_x + 8]
                    y3_block = y_plane[mb_y + 8:mb_y + 16, mb_x + 8:mb_x + 16]

                    yuv_data[index:index + y0_block.size] = y0_block.ravel()
                    index += y0_block.size
                    yuv_data[index:index + y1_block.size] = y1_block.ravel()
                    index += y1_block.size
                    yuv_data[index:index + y2_block.size] = y2_block.ravel()
                    index += y2_block.size
                    yuv_data[index:index + y3_block.size] = y3_block.ravel()
                    index += y3_block.size

            return yuv_data

        def align_data(self, value, align):
            new_value = -(-value // align) * align
            pad_length = new_value - value
            return pad_length

        def quantize_image_array(self, image_array, num_bins):
            height, width, channels = image_array.shape
            flattened_array = image_array.reshape(-1, channels).astype(np.float32)
            bin_edges = np.linspace(0, 255, num_bins + 1)
            quantized_array = np.copy(flattened_array)
            for c in range(channels):
                quantized_values = np.digitize(flattened_array[:, c], bin_edges) - 1
                quantized_array[:, c] = bin_edges[quantized_values]
            return quantized_array.reshape(height, width, channels).astype(np.uint8)


        def write_pvp(self, palette, colors, pvptrim, px_mode, pvpbank, image_path, out_dir=None):
            ttl_entries = len(palette) // 3 if pvptrim else colors
            padding = ttl_entries - len(palette) // 3

            # initialize target palette
            new_palette = []

            # handle different px_modes
            if px_mode == '565':
                palette_array = np.array(palette).reshape(-1, 3).astype(np.uint32)
            else:
                # add alpha channel to each RGB triplet
                for i in range(0, len(palette), 3):
                    r, g, b = palette[i:i + 3]
                    a = 255
                    new_palette.extend([r, g, b, a] if px_mode != '8888' else [a, r, g, b])

                palette_array = np.array(new_palette).reshape(-1, 4).astype(np.uint32)

            # convert palette to respective pixel format
            if px_mode == '1555':
                pal_mode, pixel_size = 0, 2
                palette_array = self.rgba_to_rgba1555(palette_array).flatten().astype(np.uint16)
            elif px_mode == '4444':
                pal_mode, pixel_size = 2, 2
                palette_array = self.rgba_to_rgba4444(palette_array).flatten().astype(np.uint16)
            elif px_mode == '565':
                pal_mode, pixel_size = 1, 2
                palette_array = self.rgb_to_rgb565(palette_array).flatten().astype(np.uint16)
            elif px_mode == '8888':
                pal_mode, pixel_size = 6, 4
                palette_array = self.rgba_to_rgba8888(palette_array).flatten().astype(np.uint32)

            # construct PVP data with padding
            pvp_data = palette_array.tobytes() + bytes(pixel_size * padding)

            # create PVP header
            pvp_header = bytearray(
                b'PVPL' +
                (pixel_size * ttl_entries + 8).to_bytes(4, 'little') +
                pal_mode.to_bytes(2, 'little') +
                (pvpbank.to_bytes(2, 'little') if pvpbank <= 63 else bytes([0x00, 0x00])) +
                bytes([0x00, 0x00]) +  # Adding the extra 0x00 bytes
                ttl_entries.to_bytes(2, 'little')
            )

            # write to file
            if self.out_dir and not self.buffer_mode and not self.nopvp:
                os.makedirs(self.out_dir, exist_ok=True)

            if not self.buffer_mode and not self.nopvp:
                with open(os.path.normpath(os.path.join(out_dir, os.path.basename(image_path)[:-4] + '.PVP')),
                          'wb') as f:
                    f.write(pvp_header + pvp_data + bytes([0x00]) * (self.align_data(len(pvp_data), 0x8)))
            else:
                self.buffer_pvp = pvp_header + pvp_data + bytes([0x00]) * (self.align_data(len(pvp_data), 0x8))
                self.get_pvp_buffer()


        def clean_alpha(self, image, w, h):
            # create a copy of the image in buffer
            image = image.copy()

            # clean unused R,G,B pixels to increase codebook quality
            pixels = image.load()

            # loop through each pixel
            for x in range(w):
                for y in range(h):
                    r, g, b, a = pixels[x, y]

                    # if the pixel is fully transparent (alpha = 0), clean the RGB channels
                    if a == 0:
                        r, g, b = 255, 255, 255  # Set to white

                    # set the pixel with cleaned RGB and original alpha
                    pixels[x, y] = (r, g, b, a)

            return image

        def codebook_create(self, clusters, size, px_mode):
            codebook = np.zeros((size, 8), dtype=np.uint8)

            if px_mode == '4444':
                for i, cluster in enumerate(clusters):
                    r = cluster[0::4]
                    g = cluster[1::4]
                    b = cluster[2::4]
                    a = cluster[3::4]
                    pixel = np.stack([r, g, b, a], axis=1)
                    color_mode = self.rgba_to_rgba4444(pixel)
                    codebook[i] = color_mode.view(np.uint8).reshape(-1)

            elif px_mode == '565':
                for i, cluster in enumerate(clusters):
                    r = cluster[0::3]
                    g = cluster[1::3]
                    b = cluster[2::3]
                    pixel = np.stack([r, g, b], axis=1)
                    color_mode = self.rgb_to_rgb565(pixel)
                    codebook[i] = color_mode.view(np.uint8).reshape(-1)

            elif px_mode == '555':
                for i, cluster in enumerate(clusters):
                    r = cluster[0::3]
                    g = cluster[1::3]
                    b = cluster[2::3]
                    pixel = np.stack([r, g, b], axis=1)
                    color_mode = self.rgb_to_rgb555(pixel)
                    codebook[i] = color_mode.view(np.uint8).reshape(-1)

            elif px_mode == '1555':
                for i, cluster in enumerate(clusters):
                    r = cluster[0::4]
                    g = cluster[1::4]
                    b = cluster[2::4]
                    a = cluster[3::4]
                    pixel = np.stack([r, g, b, a], axis=1)
                    color_mode = self.rgba_to_rgba1555(pixel)
                    codebook[i] = color_mode.view(np.uint8).reshape(-1)

            elif px_mode == 'yuv422':
                for i, cluster in enumerate(clusters):
                    reshaped_cluster = cluster.reshape(4, 3)  # shape to (4, 3) where each is an RGB pixel
                    Y, U, V = self.rgb_to_yuv422(reshaped_cluster)
                    yuv_code = np.array([
                        (Y[0] << 8) | U[0],  # Y0 with U from pair 0-2
                        (Y[1] << 8) | U[1],  # Y1 with U from pair 1-3
                        (Y[2] << 8) | V[0],  # Y2 with V from pair 0-2
                        (Y[3] << 8) | V[1]  # Y3 with V from pair 1-3
                    ])
                    codebook[i] = np.array(yuv_code, dtype=np.uint16).view(np.uint8).reshape(-1)

            elif px_mode == 'bump':

                for i, cluster in enumerate(clusters):
                    r = cluster[0::3]
                    g = cluster[1::3]
                    b = cluster[2::3]
                    rgb_array = np.stack((r, g, b), axis=-1)
                    sr_values = self.rgb_to_sr(rgb_array)
                    codebook[i] = sr_values.view(np.uint8).reshape(-1)

            if len(codebook) < size:
                codebook = np.vstack([codebook, np.full((size - len(codebook), 8), 0x00, dtype=np.uint8)])
            return codebook

        # post-K-means cluster rotation!
        def twiddleVQ(self, height, width):

            height = int(height)
            width = int(width)

            values = np.zeros((height, width), dtype=np.uint32)
            y, x = np.meshgrid(np.arange(height), np.arange(width), indexing='ij')
            max_dim = max(height, width).bit_length()

            for i in range(max_dim):
                values |= ((x >> i) & 1).astype(np.uint32) << (2 * i)
                values |= ((y >> i) & 1).astype(np.uint32) << (2 * i + 1)

            return values

        def generate_mipmaps(self, image, fmt, tex_mode):
            resampling = Image.LANCZOS if not self.nearest else Image.NEAREST
            mipmaps = [image]
            width, height = image.size

            # generate mipmaps
            while width > 1 and height > 1:
                width = max(width // 2, 1)
                height = max(height // 2, 1)
                mipmaps.append(image.resize((width, height), resampling))

            # create a new image with the same height but double the width
            max_height = max(mipmap.size[1] for mipmap in mipmaps)
            combined_width = 2 * max_height

            combined_image = Image.new(fmt, (combined_width, max_height))
            # apply the palette after creating the new image

            combined_array = np.array(combined_image)

            if 'vq' in tex_mode:
                # create background pattern reusing a single codebook entry
                block = image.crop((0, 0, 2, 2))
                block_array = np.array(block)
                background_array = np.tile(block_array, (max_height // 2, combined_width // 2, 1))

                # place background pattern
                combined_array[:background_array.shape[0], :background_array.shape[1]] = background_array

            # place each mipmap in the new image
            x_offset, y_offset = 0, 0
            for mipmap in mipmaps:
                mipmap_array = np.array(mipmap)
                if x_offset + mipmap_array.shape[1] > combined_width:
                    y_offset += mipmap_array.shape[0]
                    x_offset = 0
                combined_array[y_offset:y_offset + mipmap_array.shape[0],
                x_offset:x_offset + mipmap_array.shape[1]] = mipmap_array
                x_offset += mipmap_array.shape[1]

            combined_image = Image.fromarray(combined_array)

            return combined_image

        def handle_twiddling(self, tex_mode, pvr_array, img_height, img_width, px_size):
            twiddled_indices = Pypvr().twiddle(img_width, img_height)
            if 'pal4' in tex_mode:
                num_bytes = (img_height * img_width) // 2
                pvr_twiddled = np.zeros(num_bytes, dtype=np.uint8)
                tw_array = np.zeros_like(pvr_array)
                tw_array[twiddled_indices] = pvr_array
                pvr_twiddled[:] = (tw_array[::2] & 0x0F) | ((tw_array[1::2] & 0x0F) << 4)
            else:
                pvr_twiddled = np.zeros(img_height * img_width, dtype=px_size)
                pvr_twiddled[twiddled_indices] = pvr_array
            return pvr_twiddled

        def array_encode(self, tex_mode, px_mode, rgb_array, num_channels, px_size, img_width, img_height):
            if 'pal4' in tex_mode or 'pal8' in tex_mode:
                pixel_values = rgb_array
            elif 'bmp' in tex_mode:
                pixel_values = self.rgba_to_rgba8888(rgb_array)
            elif px_mode == 'bump':
                pixel_values = self.rgb_to_sr(rgb_array)
            elif px_mode == '565':
                pixel_values = self.rgb_to_rgb565(rgb_array)
            elif px_mode == '555':
                pixel_values = self.rgb_to_rgb555(rgb_array)
            elif px_mode == '1555':
                pixel_values = self.rgba_to_rgba1555(rgb_array)
            elif px_mode == '4444':
                pixel_values = self.rgba_to_rgba4444(rgb_array)
            elif px_mode == 'yuv422':
                pixel_values = self.encode_yuv422(rgb_array, num_channels, px_size)
            elif px_mode == 'yuv420':
                pixel_values = self.encode_yuv420(img_width, img_height, rgb_array)

            pvr_array = pixel_values.flatten().astype(px_size)

            if 'tw' in tex_mode or 'pal' in tex_mode or 'twal' in tex_mode:
                pvr_array = self.handle_twiddling(tex_mode, pvr_array, img_height, img_width, px_size)

            return pvr_array.tobytes()

        def encode_pvr(self, image, flip, width, height, fmt, colors, tex_mode, px_mode, gbix, gitrim, pvptrim, pvpbank,
                       vq_iter, vq_rseed, image_path, out_dir=None):
            if not self.silent:print(
                f'Encoding [{(self.tex_mode).upper()}][{(self.px_mode).upper()}]'
                f'{f"[GBIX {self.gbix}]" if self.gbix is not None else ""}'
                f'{f"[GBIX_TRIM]" if self.gitrim is not False else ""}'
                f'{f"[PVP_BANK {self.pvpbank}]" if self.pvpbank is not None and "pal" in self.tex_mode else ""}'
                f'{f"[PVP_TRIM]" if self.pvptrim and "pal" in self.tex_mode else ""}'
                fr'File: {os.path.normpath(os.path.join(out_dir, os.path.basename(image_path)[:-4] + ".PVR"))}'
            )

            start_time = time.time()

            if flip:
                image = image.transpose(Image.FLIP_TOP_BOTTOM)

            if 'pal8' in tex_mode or 'pal4' in tex_mode:
                palette = image.getpalette()

            if 'mm' in tex_mode:
                image = self.generate_mipmaps(image, fmt, tex_mode)

            if 'vq' in tex_mode or 'svq' in tex_mode:

                # adjust image to compensate for k-means rearrangement
                image = image.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
                image_array = np.array(image)

                # quantize the image array before compression
                image_array = self.quantize_image_array(image_array, 256)

                codebook, labels = self.compress_vq_buffer(image_array, px_mode, tex_mode, vq_iter,
                                                           vq_rseed,
                                                           height, width)

                pvr_data = bytes(codebook.tobytes() + labels.astype(np.uint8).tobytes())

            else:
                # set the number of channels based on pixel mode
                num_channels = 4 if px_mode in ['4444', '1555', '8888'] else 3

                # set pixel mode based on tex_mode
                if 'pal8' in tex_mode or 'pal4' in tex_mode:

                    num_channels = 4
                    px_size = np.uint8
                    if 'p4bpp' in px_mode or 'p8bpp' in px_mode:
                        pass
                    else:
                        self.write_pvp(palette, colors, pvptrim, px_mode, pvpbank, image_path, out_dir)

                elif px_mode not in ['8888', 'yuv420'] and 'bmp' not in tex_mode:
                    px_size = np.uint16
                elif 'yuv420' in px_mode:
                    px_size = np.uint8
                else:
                    px_size = np.uint32

                pixels = np.array(image)

                # initialize PVR data
                if 'mm' in tex_mode:

                    level, x_start, current_size = 0, 0, height
                    pvr_data_list = []  # list to store pvr_data for each level

                    while current_size >= 1:
                        if self.debug: print(f'current_size: {current_size} x_start: {x_start}')

                        # extract, save the mipmap level, and prepare for the next
                        mipmap_part = pixels[0:current_size, x_start:x_start + current_size].reshape(-1,
                                                                                                     1 if 'pal' in tex_mode else num_channels).astype(
                            np.uint32)

                        # prepend new pvr_data to the list
                        new_pvr_data = self.array_encode(tex_mode,
                                                         '565' if current_size == 1 and 'yuv422' in px_mode else px_mode,
                                                         mipmap_part, 1 if 'pal' in tex_mode else num_channels, px_size,
                                                         current_size,
                                                         current_size)

                        pvr_data_list.insert(0, new_pvr_data)

                        # update for the next level
                        x_start += current_size
                        current_size //= 2
                        level += 1

                    # padding for mips data alignment
                    if px_mode == '8888':
                        pad = b'\x00' * 4
                    elif 'twal' in tex_mode:
                        pad = b'\x00' * 6
                    elif 'pal8' in tex_mode:
                        pad = b'\x00' * 3
                    else:
                        pad = b'\x00' * 2

                    # concatenate all pvr_data
                    pvr_data = pad + b''.join(pvr_data_list)

                else:
                    # convert to PVR data without mipmaps
                    rgb_array = pixels.reshape(-1, num_channels).astype(px_size)
                    pvr_data = self.array_encode(tex_mode, px_mode, rgb_array, num_channels, px_size, width, height)

            end_time = time.time()
            elapsed_time = end_time - start_time

            if not self.silent:print(f"Time taken to encode: {elapsed_time:.3f} seconds")

            if not self.buffer_mode:
                self.write_pvr(image_path, pvr_data, tex_mode, px_mode, width, height, gbix, gitrim, out_dir)
            else:
                self.buffer_pvr = self.write_pvr(image_path, pvr_data, tex_mode, px_mode, width, height, gbix, gitrim, out_dir)

        def get_pvr_buffer(self):
            return self.buffer_pvr

        def get_pvp_buffer(self):
            return self.buffer_pvp

        def vq_algo1(self,blocks, n_clusters, max_iter=100, seed=None):
            if seed is not None:
                np.random.seed(seed)

            n_samples, n_features = blocks.shape

            # float32 to avoid overflow
            blocks_float = blocks.astype(np.float32)

            # optimized L2 distance calculation using matrix multiplication
            def compute_distances(blocks, centroids):
                # squared norm of each block and centroid
                blocks_norm = np.sum(blocks ** 2, axis=1)[:, np.newaxis]
                centroids_norm = np.sum(centroids ** 2, axis=1)[np.newaxis, :]

                # dot product between blocks and centroids
                dot_product = np.dot(blocks, centroids.T)

                # euclidean squared distance
                distances = blocks_norm + centroids_norm - 2 * dot_product
                return distances

            # optimized K-means initialization
            def kmeans_init(blocks, n_clusters):
                centroids = np.zeros((n_clusters, n_features), dtype=np.float32)

                # choose first centroid randomly
                centroids[0] = blocks[np.random.randint(n_samples)]

                # initialize distances array
                distances = np.sum((blocks - centroids[0]) ** 2, axis=1)

                # choose remaining centroids
                for i in range(1, n_clusters):
                    # normalize distances to get probabilities
                    if np.sum(distances) > 0:
                        probabilities = distances / distances.sum()
                        next_centroid_idx = np.random.choice(n_samples, p=probabilities)
                    else:
                        next_centroid_idx = np.random.randint(n_samples)

                    centroids[i] = blocks[next_centroid_idx]

                    # update distances - only compute for the new centroid
                    new_distances = np.sum((blocks - centroids[i]) ** 2, axis=1)
                    distances = np.minimum(distances, new_distances)

                return centroids

            # initialize centroids using K-means++
            centroids = kmeans_init(blocks_float, n_clusters)

            # pre-allocate arrays
            old_centroids = np.zeros_like(centroids)
            counts = np.zeros(n_clusters, dtype=np.int32)

            # main K-means loop
            for _ in range(max_iter):
                # store old centroids for convergence check
                old_centroids[:] = centroids

                # assign labels using vectorized distance computation
                distances = compute_distances(blocks_float, centroids)
                labels = np.argmin(distances, axis=1)

                # reset centroids and counts
                centroids.fill(0)
                counts.fill(0)

                # update centroids using numpy!
                np.add.at(centroids, labels, blocks_float)
                np.add.at(counts, labels, 1)

                # update centroids, handling empty clusters
                mask = counts > 0
                centroids[mask] = centroids[mask] / counts[mask, np.newaxis]

                # handle empty clusters
                empty_clusters = ~mask
                if np.any(empty_clusters):
                    # assign random points to empty clusters
                    n_empty = np.sum(empty_clusters)
                    random_indices = np.random.choice(n_samples, size=n_empty, replace=False)
                    centroids[empty_clusters] = blocks_float[random_indices]

                # check for convergence
                if np.array_equal(old_centroids, centroids):
                    break

            # convert centroids back to the original data type
            centroids = np.clip(np.round(centroids), 0, 255).astype(blocks.dtype)

            return centroids, labels


        def compress_vq_buffer(self, image_array, px_mode, tex_mode, vq_iter,vq_rseed, height, width):

            # setup image parameters and preprocessing
            num_channels = 4 if px_mode in ['4444', '1555'] else 3
            if height % 2 != 0 or width % 2 != 0 or height < 8 or width < 8:
                raise ValueError("VQ image dimensions must be power of 2 and no smaller than 8x8 pixels")

            if 'svq' in tex_mode:
                if self.debug: print('SmallVQ')
                if height not in {8, 16, 32, 64}:
                    raise ValueError('SmallVQ dimensions range 8px <--> 64px')
                codebook_size = \
                    {8: 16, 16: 16, 32: 64 if 'mm' in tex_mode else 32, 64: 256 if 'mm' in tex_mode else 128}[height]
            elif 'vq' in tex_mode:
                if self.debug: print('vq')
                codebook_size = 256

            if self.debug: print('codebook size:', codebook_size)

            n_clusters = codebook_size if 'svq' in tex_mode else (
                    height * (4 if 'mm' in tex_mode else 2)) if height < 32 else 256

            if 'mm' in tex_mode:
                blocks = image_array.reshape((width*2) // 2, 2, height // 2, 2, num_channels)
            else:
                blocks = image_array.reshape(height // 2, 2, width // 2, 2, num_channels)

            blocks = blocks.transpose(0, 2, 1, 3, 4).reshape(-1, 2 * 2 * num_channels)

            # auto select VQ algo
            if self.vqalgo is None:
                self.vqalgo = 'vqa2' if width > 256 else 'vqa1'

            if self.vqalgo == 'vqa1':
                if not self.silent: print('VQ Compression [VQA1]...')
                clusters, labels = self.vq_algo1(blocks, n_clusters, max_iter=vq_iter,seed=vq_rseed)

            elif self.vqalgo == 'vqa2':
                import faiss
                if not self.silent: print('VQ Compression [VQA2]...')

                # setup FAISS K-means
                blocks = blocks.astype(np.float32)  # FAISS requires float32 input
                kmeans = faiss.Kmeans(d=blocks.shape[1], k=n_clusters, niter=vq_iter, seed=vq_rseed)

                # train the K-means model
                kmeans.train(blocks)

                clusters = kmeans.centroids.astype(np.uint8)
                _, labels = kmeans.index.search(blocks, 1)
                labels = labels.flatten()

            codebook = self.codebook_create(clusters, codebook_size, px_mode)


            if 'mm' in tex_mode:
                # number of MIP levels
                mip_level = int(np.log2(width))

                # initialize arrays with the correct size
                mip_height = np.zeros(mip_level, dtype=int)
                mip_start = np.zeros(mip_level, dtype=int)
                end_index = np.zeros(mip_level, dtype=int)

                # calculate mip_height, mip_start, and end_index in a single loop
                start_offset = 0
                for i in range(mip_level):
                    index = mip_level - 1 - i
                    height = (width // 2) >> i
                    mip_height[index] = height

                    # calculate the end offset based on the current mip level height
                    end_offset = start_offset + (height * height << i)
                    mip_start[index] = start_offset
                    end_index[index] = end_offset

                    # update start_offset for the next iteration
                    start_offset = end_offset

                # calculate total_size
                mip_height_squared = mip_height ** 2
                total_size = np.sum(mip_height_squared)
                index = np.zeros(total_size, dtype=labels.dtype)

                mip_offset = 0

                # process mip data in the forward order
                for i in range(mip_level):
                    current_mip_height = mip_height[i]
                    step = width // 2 // current_mip_height

                    # reshape the relevant portion of the array
                    grid = labels[mip_start[i]:end_index[i]].reshape(((width*2) // 4, current_mip_height))

                    # slice and flatten
                    mip_data = grid[::step, :current_mip_height].flatten()

                    # twiddle the labels
                    indices = self.twiddleVQ(current_mip_height, current_mip_height).ravel()
                    labels_twiddled = np.zeros(current_mip_height * current_mip_height, dtype=mip_data.dtype)
                    labels_twiddled[indices] = mip_data

                    # copy to the result array
                    size = current_mip_height * current_mip_height
                    index[mip_offset:mip_offset + size] = labels_twiddled
                    mip_offset += size

                # padding and concatenation
                index = np.pad(index, (1, 0), mode='constant')

            else:
                # no Mips!
                labels_twiddled = np.zeros(height //2 * width // 2, dtype=labels.dtype)
                labels_twiddled[self.twiddleVQ(height // 2, width // 2).ravel()] = labels
                index = labels_twiddled

            return codebook, index

        def write_pvr(self, image_path, pvr_data, tex_mode, px_mode, width, height, gbix, gitrim, out_dir=None):

            padding = self.align_data(len(pvr_data), 0x4)
            pvr_data += bytes(b'\x00' * padding)

            # write PVR
            pvr_size = len(pvr_data) + 8
            mode_num = (list(Pypvr().px_modes.keys())[list(Pypvr().px_modes.values()).index(px_mode)]).to_bytes(1,
                                                                                                                'little')
            tex_num = (list(Pypvr().tex_modes.keys())[list(Pypvr().tex_modes.values()).index(tex_mode)]).to_bytes(1,
                                                                                                                  'little')

            pvr_header = bytearray(
                b'PVRT' +
                pvr_size.to_bytes(4, 'little') +
                mode_num + tex_num +
                bytes([0x00, 0x00]) +
                width.to_bytes(2, 'little') +
                height.to_bytes(2, 'little')
            )

            # GBIX handling
            if gbix is not None:
                # ensure gbix is within valid range and create GBIX header with optional padding
                gbix = min(gbix, 0xFFFFFFFF)
                gbix_header = bytearray(
                    b'GBIX' + (4 if gitrim else 8).to_bytes(4, 'little') + gbix.to_bytes(4, 'little'))

                if not gitrim:
                    gbix_header.extend(b'\x00' * 4)  # append padding if gbix trim is False

                pvr_header = gbix_header + pvr_header  # prepend gbix header to pvr header

            if self.out_dir and not self.buffer_mode:
                os.makedirs(self.out_dir, exist_ok=True)

            # write to the PVR file
            if not self.buffer_mode:
                with open(os.path.normpath(os.path.join(out_dir, os.path.basename(image_path)[:-4] + '.PVR')),
                          'wb') as f:
                    f.write(pvr_header + pvr_data)
            else:
                pvr_data_buffer = pvr_header + pvr_data
                return pvr_data_buffer


        def load_image(self, image, image_path, flip, tex_mode, px_mode, gbix, gitrim, pvptrim, pvpbank, vq_iter,
                       vq_rseed, out_dir=None,colors = None):


            if 'pal8' in tex_mode:
                fmt = 'P'
                colors = 256
            elif 'pal4' in tex_mode:
                fmt = 'P'
                colors = 16
            elif px_mode in ('4444', '1555') or 'bmp' in tex_mode:
                fmt = 'RGBA'
            elif px_mode in ('555', '565', 'yuv422', 'yuv420', 'bump'):
                fmt = 'RGB'


            # handle palette quantization if applicable
            if colors:
                if image.mode == 'P' and len(image.getpalette()) // 3 <= colors:
                    pass  # no need to quantize if the palette is already within the color limit
                else:
                    image = image.quantize(colors=colors, dither=0)  # quantize without dithering

            image = image.convert(fmt)
            width, height = image.size

            self.encode_pvr(image, flip, width, height, fmt, colors, tex_mode, px_mode, gbix, gitrim, pvptrim, pvpbank,
                            vq_iter,vq_rseed, image_path, out_dir)


        def process_pvr_log(self, log_file):
            # process pvr_log.txt file to re-encode

            with open(log_file, 'r') as file:
                content = file.read().strip().split('---------------')

                for entry in content:
                    lines = entry.strip().split('\n')
                    image_file = None
                    target_pvr = None
                    enc_params = None
                    data_crc32 = None
                    cnt_filnam = None
                    cnt_offset = None
                    data_fsize = None
                    pvr_filenm = None

                    for line in lines:
                        # extract the key-values
                        if line.startswith("IMAGE FILE :") or line.startswith("IMAGE FILE:"):
                            image_file = line.split(":", 1)[1].strip()
                        elif line.startswith("TARGET DIR :") or line.startswith("TARGET DIR:"):
                            target_pvr = line.split(":", 1)[1].strip()
                        elif line.startswith("ENC PARAMS :") or line.startswith("ENC PARAMS:"):
                            enc_params = line.split(":", 1)[1].strip()
                        elif line.startswith("DATA CRC32 :") or line.startswith("DATA CRC32:"):
                            data_crc32 = line.split(":", 1)[1].strip()
                        elif line.startswith("PVR FILE   :") or line.startswith("PVR FILE:") or \
                                line.startswith("PVP FILE   :") or line.startswith("PVP FILE:"):
                            pvr_filenm = line.split(":", 1)[1].strip()
                        elif line.startswith("CONTAINER  :") or line.startswith("CONTAINER:"):
                            cnt_filnam = line.split(":", 1)[1].strip()
                        elif line.startswith("DATA OFFST :") or line.startswith("DATA OFFST:"):
                            cnt_offset = int(line.split(":", 1)[1].strip())
                        elif line.startswith("DATA FSIZE :") or line.startswith("DATA FSIZE:"):
                            data_fsize = int(line.split(":", 1)[1].strip())

                    if data_crc32 is None:
                        data_crc32 = '0'

                    # if we have container info but no image processing info, treat as PVP-only case
                    if all([pvr_filenm, cnt_filnam, cnt_offset, data_fsize]) and not all(
                            [image_file, target_pvr, enc_params, data_crc32]):
                        try:
                            # read the PVP file
                            with open(pvr_filenm, 'rb') as pvp_file:
                                pvp_data = pvp_file.read()

                            # check if file size matches
                            if len(pvp_data) > data_fsize:
                                print(f"Error: PVP file '{pvr_filenm}' is larger than the specified size!")
                                continue

                            # import back to container
                            with open(cnt_filnam, 'rb+') as container:
                                container.seek(cnt_offset)
                                container.write(pvp_data)
                            continue

                        except FileNotFoundError as e:
                            print(f"Error: File not found - {str(e)}")
                            continue
                        except IOError as e:
                            print(f"Error: IO operation failed - {str(e)}")
                            continue
                        except Exception as e:
                            print(f"Error: Unexpected error occurred - {str(e)}")
                            continue

                    # check if pvr_log.txt have all required parameters
                    if image_file and target_pvr and enc_params and data_crc32:
                        try:
                            with open(image_file, 'rb') as c:
                                calculated_crc32 = hex(zlib.crc32(c.read()))[2:].upper()

                        except FileNotFoundError:
                            print(f"Error: Image file '{image_file}' not found.")
                            continue

                        # check for different image CRC32 to determine if necessary to encode or skip
                        if calculated_crc32 != data_crc32:
                            Pypvr.Encode(f'{image_file} {enc_params} -o {target_pvr}')

                            # after encoding, check if we need to process container
                            if all([pvr_filenm, cnt_filnam, cnt_offset, data_fsize]):
                                try:
                                    # read the encoded PVR file
                                    with open(pvr_filenm, 'rb') as pvr_file:
                                        pvr_data = pvr_file.read()

                                    # check if file size matches
                                    if len(pvr_data) > data_fsize:
                                        print(f"Error: Encoded file '{pvr_filenm}' is larger than the specified size!")
                                        continue

                                    # open container and write data
                                    with open(cnt_filnam, 'rb+') as container:
                                        container.seek(cnt_offset)
                                        container.write(pvr_data)

                                except FileNotFoundError as e:
                                    print(f"Error: File not found - {str(e)}")
                                except IOError as e:
                                    print(f"Error: IO operation failed - {str(e)}")
                                except Exception as e:
                                    print(f"Error: Unexpected error occurred - {str(e)}")
                        else:
                            if not self.silent: print(f"Skipping '{image_file}': same image CRC32!")

    class Cli:
        def __init__(self, args=None):

            if len(sys.argv) > 1:
                args = sys.argv[1:]

                if len(sys.argv) == 2 and args == ['-h']:
                    self.help_text()
                    sys.exit(1)

                files_to_process = []
                output_dir = None
                additional_args = []
                decode_files = []

                i = 0
                while i < len(args):
                    if args[i] == '-o':
                        if i + 1 < len(args) and not args[i + 1].startswith('-'):
                            output_dir = args[i + 1]
                            additional_args.extend([args[i], args[i + 1]])
                            i += 1
                        else:
                            print("Error: No output directory specified after '-o'.")
                            sys.exit(1)
                    elif args[i].startswith('-'):  # command-line options
                        additional_args.append(args[i])
                        if i + 1 < len(args) and not args[i + 1].startswith('-'):
                            additional_args.append(args[i + 1])
                            i += 1
                    else:
                        # expand wildcard patterns
                        matched_files = self.list_files_with_extensions(args[i])
                        files_to_process.extend(matched_files)
                    i += 1

                if not files_to_process:
                    print("No files provided to process!")
                    sys.exit(1)

                # process each file with check_file_type
                for file in files_to_process:
                    output_dir_for_file = output_dir or os.getcwd()
                    self.check_file_type(file, output_dir_for_file, additional_args, decode_files)

                # process all decode files together
                if decode_files:

                    quoted_decode_files = [f'"{file}"' for file in decode_files]
                    combined_args = quoted_decode_files + additional_args

                    # pass all decode files together for decoding
                    Pypvr.Decode(' '.join(combined_args))

            else:
                # print help/usage information if no arguments
                print('      ____        ____ _    ______')
                print('     / __ \\__  __/ __ \\ |  / / __ \\   V.1.0')
                print('    / /_/ / / / / /_/ / | / / /_/ /')
                print('   / ____/ /_/ / ____/| |/ / _, _/ ')
                print('  /_/    \\__, /_/     |___/_/ |_|  ')
                print('        /____/                    ')
                print('---------------------------------------------')
                print('  Unofficial PowerVR2 Python Image Processor ')
                print('---------------------------------------------')
                print('             2025 VincentNL             ')
                print('       github.com/VincentNLOBJ/pypvr')
                print('---------------------------------------------')
                print("  ♥ ko-fi.com/vincentnl")
                print("  ♥ patreon.com/vincentnl")
                print('---------------------------------------------')
                print('  For HELP and USAGE OPTIONS:')
                print('       > pypvr.exe -h')
                print(' ----------------------------')

        def list_files_with_extensions(self, pattern):
            directory = os.path.dirname(pattern) or '.'  # default to current directory if no directory is provided
            pattern = os.path.basename(pattern)  # get the base name of the pattern (e.g., "*.png")

            matched_files = []

            try:
                files = os.listdir(directory)
            except FileNotFoundError:
                print(f"Directory not found: {directory}")
                return []

            # filter files based on the pattern
            for filename in fnmatch.filter(files, pattern):
                matched_files.append(os.path.abspath(os.path.join(directory, filename)))  # full path

            return matched_files

        def check_file_type(self, file_name, output_dir, extra_args, decode_files):
            # input file should be encoded / decoded based on its extension

            base_file_name = os.path.basename(file_name)
            combined_args = [file_name, '-o', output_dir] + extra_args  # arguments for encoding/decoding

            # check for pvr_log.txt (special case)
            if base_file_name.lower() == 'pvr_log.txt':
                Pypvr.Encode().process_pvr_log(file_name)

            # check if the file is one of the decode file types
            elif base_file_name.lower().endswith(('.pvp', '.pvr', '.dat', '.bin', '.pvm', '.tex', 'mun')):
                decode_files.append(file_name)  # add to decode list

            # check if the file is an image format (should be encoded)
            elif base_file_name.lower().endswith(('.png', '.gif', '.bmp', '.tga', '.jpg', '.tif')):
                Pypvr.Encode(' '.join(combined_args))  # process as an image for encoding

            else:
                print(f"{file_name}: Unknown file format! Please check the file type.")

        def help_text(self):
            print('   ------------------------')
            print('   # PyPVR HELP AND USAGE #')
            print('   ------------------------')
            print('   1. DECODE: PVR --> IMG ')
            print('   2. DECODE OPTIONS')
            print('   3. ENCODE: IMG --> PVR')
            print('   4. ENCODE OPTIONS')
            print('   5. EXAMPLES')
            print()
            print('   -----------------------')
            print('   1. DECODE: PVR --> IMG ')
            print('   -----------------------')
            print('  Convert one or more .PVR file and save them as .PNG or BMP.')
            print('  .PVP palette will be converted to Adobe Color Table (ACT).')
            print('  ** Note **')
            print('  If a .PVP and .PVR file with the same name are present, the palette will be applied to the image.')
            print()
            print('  Usage:')
            print('    > pypvr.exe <infile1.PVR> -<options>')
            print()
            print('   -----------------')
            print('   2. DECODE OPTIONS')
            print('   -----------------')
            print('    fmt <img_format>    # Image format: png | bmp')
            print('    o <out_dir>         # Output directory')
            print('    flip                # Flip vertically')
            print('    silent              # No screen prints')
            print('    log                 # Create a pvr_log.txt for later re-import')
            print('    dbg                 # Debug mode')
            print('    usepal <pvp_file>   # Decode palettized image with colors from a pvp palette')
            print('    act                 # Convert PVP to ACT palette (Adobe Color Table)')
            print('    nopvp               # Do not extract pvp')
            print()
            print()
            print('   ----------------------')
            print('   3. ENCODE: IMG --> PVR')
            print('   ----------------------')
            print('  Encode an image to .PVR and .PVP if palettized.')
            print()
            print('  Usage:')
            print('    > pypvr.exe <infile> -<options>')
            print()
            print('   -----------------')
            print('   4. ENCODE OPTIONS')
            print('   -----------------')
            print('    <color_format>')
            print('      * Note: YUV420 / BMP / 555 texture formats use DC/Naomi SEGA libraries for conversion.')
            print('     --------------------------------------------------------------------------------------')
            print('      PARAM  |     COLOR TYPE    |                      DESCRIPTION')
            print('     --------|-------------------|---------------------------------------------------------')
            print('      565    | RGB               | Ideal for gradients, no transparency support')
            print('      1555   | ARGB 1-bit alpha  | Use when image has fully opaque or transparent alpha ')
            print('      4444   | ARGB 4-bit alpha  | Lower accuracy but supports complex transparency.')
            print('      8888   | ARGB 8-bit alpha  | Used by pal4, pal8, BMP; supports full transparency')
            print('      yuv422 | YUV422            | Lossy format with higher perceived color gamut')
            print('      bump   | RGB Normal map    | Height map converted to SR')
            print('      555    | RGB PCX converter | !WARNING! Use 1555 mode instead')
            print('      yuv420 | YUV420 converter  | !WARNING! Used by YUV converter or .SAN files')
            print('      p4bpp  | 4-bpp placeholder | !WARNING! Color format in palette file')
            print('      p8bpp  | 8-bpp placeholder | !WARNING! Color format in palette file')
            print()
            print()
            print('    <texture_format>')
            print('      * Note: Twiddled offers fast performance and high-fidelity colors on hardware.')
            print('     --------------------------------------------------------------------------------------')
            print('      PARAM  |   TEXTURE TYPE     |   TWIDDLED   |       DESCRIPTION            |  MIPMAPS  ')
            print('     --------|--------------------|---------------------------------------------------------')
            print('      tw     | Square             |   Twiddled   | Square dimensions only       |    YES')
            print('      twre   | Rectangle          |   Twiddled   | Length, width multiples      |    NO ')
            print('      re     | Rectangle          | Not Twiddled | Length, width multiples      |    NO ')
            print('      st     | Stride             | Not Twiddled | Width multiple of 32 (32-992)|    NO ')
            print('      twal   | Alias              |   Twiddled   | Square dims. and Mips <= 8x8 |    YES')
            print('      pal4   | 16-colors palette  |   Twiddled   | Square dimensions only       |    YES')
            print('      pal8   | 256-colors palette |   Twiddled   | Square dimensions only       |    YES')
            print('      vq     | Vector Quantized   |   Twiddled   | Square dimensions only       |    YES')
            print('      svq    | Small VQ           |   Twiddled   | Square dimensions <= 64x64   |    YES')
            print('      bmp    | Bitmap             | Not Twiddled | Square dimensions only       |    YES')
            print()
            print()
            print('   <other_options>')
            print('    mm            | Generate Mipmaps')
            print('    near          | Force nearest resampling for Mipmaps, default is Bilinear')
            print('    flip          | Vertical image flip')
            print('    cla           | Clean unused RGB from alpha channel')
            print('    gi <n>        | Specify GBIX header value')
            print('    gitrim        | Short GBIX header, saves 4 bytes')
            print('    pvptrim       | Remove unused colors of a 16 or 256 palette')
            print('    pvpbank <n>   | Specify PVP palette bank number from 0-63')
            print('    nopvp         | Do not create PVP file')
            print('    vqa1          | VQ Algo 1 - better for details, slower encoding speed for large images')
            print('    vqa2          | VQ Algo 2 - better for gradients, fast faiss algo')
            print('    vqi <n>       | VQ iterations: 10 is default value, increase for sharper details')
            print('    vqs <n>|rand  | VQ random seed: value or random, changing it will alter compression artifacts')
            print()
            print()
            print('   -----------')
            print('   5. EXAMPLES')
            print('   -----------')
            print()
            print('        ----------------------')
            print('  ---- | CONVERT PVR TO IMAGE |')
            print('        ----------------------')
            print()
            print('  Example 1 - Convert a PVR to default image format (.png):')
            print('    > pypvr.exe "file1.PVR"')
            print()
            print('  Example 2 - Convert all .PVR files to images, save in "c:\\images", create log file for reimport :')
            print('    > pypvr.exe "*.pvr" -o "c:\\images"')
            print()
            print('  Example 3 - Convert a PVR to image, Vertical flip, save in "c:\\decoded" directory:')
            print('    > pypvr.exe "infile1.PVR" -png -flip -o "c:\\decoded"')
            print()
            print()
            print('        ----------------------')
            print('  ---- | CONVERT IMAGE TO PVR |')
            print('        ----------------------')
            print()
            print('  Example 1 - Convert image to PVR, default settings:')
            print('    > pypvr.exe "test.png"')
            print()
            print('  Example 2 - Automatically re-encode all images back to PVR(s) as per pvr_log.txt:')
            print('    > pypvr.exe "c:\\image_dir\\pvr_log.txt"')
            print()
            print('  Example 3 - Convert all .png images to .PVR(s), save them to output folder "c:\\pvr_dir" :')
            print('    > pypvr.exe "*.png" -o "c:\\pvr_dir"')
            print()
            print('  Example 4 - Convert image to 1555 twiddled, use Global Index 0:')
            print('    > pypvr.exe "test.png" -1555 -tw -gi 0')
            print()
            print('  Example 5 - Convert image to 565, VQ compress')
            print('    > pypvr.exe "test.png" -565 -vq')
            print()
            print()
            print('        -----------------------------')
            print('  ---- | BINARY CONTAINER EXTRACTION |')
            print('        -----------------------------')
            print()
            print('  Example 1 - Scan a binary file for PVR / PVP data')
            print('    > pypvr.exe "unknown.DAT"')
            print()
            print()
            print('        --------------------------')
            print('  ---- | BINARY CONTAINER REBUILD |')
            print('        --------------------------')
            print()
            print('  Example 1 - Reimport modified images and palettes back to container using log file:')
            print('    > pypvr.exe "c:\\myfolder\\"pvr_log.txt"')
            print()
            print()

if __name__ == "__main__":
    Pypvr.Cli()
