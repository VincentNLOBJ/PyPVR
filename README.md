<p align="center">
  <img src="https://github.com/user-attachments/assets/187425e7-e73a-4b8c-801b-ee2126db0e30">
</p>

# PyPVR - Unofficial PVR Image Tool

`PyPVR` is a modern Python tool for encoding / decoding PowerVR2 images used by `SEGA Naomi` and `SEGA Dreamcast`.
All texture modes, pixel formats, palettes and PVR variations used by SEGA's SDK are supported.

Created to easily modify DC game images without resorting to licensed programs from SDKs.
1. Convert `.PVR` to `.png` by drag & drop.
2. Edit images
3. Feed `PyPVR` with `pvr_log.txt` and it'll take care of encoding all extracted images. As simple as that!

## Main Features
- Pyhon 3.9.12+, OS free!
- Portable Windows application
- Drag and drop interface for both `encode` / `decode` / `binary extraction` / `reimport`.
![extract drag](https://github.com/user-attachments/assets/614339a3-bd05-4587-b9e6-b896fba87513)
- Complete command line tool
- 2 VQ quality algorithms to provide a flexible solution according to your needs.
![PYPVR_VQMM](https://github.com/user-attachments/assets/98b84dbf-0e56-4366-9277-80a6223647e4)
- Palette color index maintained during conversion
- Automated CRC32 encode skip if .png file is the same
- Simple and editable `.txt` log file for automated encoding!
- YUV420 encoding, Bump map supported!


## ♥ Support ♥
- https://ko-fi.com/vincentnl
- https://ko-fi.com/patreon.com/vincentnl

## Credits

 - Tcaw for K-means idea leading to quality VQ encoding
 - Egregiousguy for YUV420 decoding 
 - Kion for SmallVQ mipmaps data
 - MetalliC for hardware knowledge
 - My daughter for logo design! ♥

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

---

## PyPVR Table of Contents
1. [DECODE: PVR --> IMG](#1-decode-pvr----img)
2. [DECODE OPTIONS](#2-decode-options)
3. [ENCODE: IMG --> PVR](#3-encode-img----pvr)
4. [ENCODE OPTIONS](#4-encode-options)
5. [EXAMPLES](#5-examples)

---

## 1. DECODE: PVR --> IMG
Convert one or more `.PVR` files and save them as `.PNG` or `.BMP`.

`.PVP` palette can be converted to Adobe Color Table `.ACT`

**Palette Note**  
If a `.PVP` and `.PVR` file with the same name are present, the palette will be applied to the image.

### Usage:
```bash
pypvr.exe <infile1.PVR> -<options>
```

---

## 2. DECODE OPTIONS
- `-fmt <img_format>`: Image format: png | bmp
- `-o <out_dir>`: Output directory
- `-flip`: Flip vertically
- `-silent`: No screen prints
- `-log`: Create a `pvr_info.txt` for later re-import
- `-dbg`: Debug mode
- `-usepal <pvp_file>`: Decode palettized image with colors from a pvp palette
- `-act`: Convert PVP to ACT palette (Adobe Color Table)
- `-nopvp`: Do not extract pvp

---

## 3. ENCODE: IMG --> PVR
Encode an image to `.PVR` and `.PVP` if palettized.

### Usage:
```bash
pypvr.exe <infile> -<options>
```

---

## 4. ENCODE OPTIONS

### <color_format>
**Note**: YUV420 / BMP / 555 texture formats use DC/Naomi SEGA libraries for conversion.

| PARAM   | COLOR TYPE        | DESCRIPTION                                      |
| ------- | ----------------- | ------------------------------------------------ |
| `-565`   | RGB               | Ideal for gradients, no transparency support    |
| `-1555`  | ARGB 1-bit alpha  | Use when image has fully opaque or transparent alpha |
| `-4444`  | ARGB 4-bit alpha  | Lower accuracy but supports complex transparency |
| `-8888`  | ARGB 8-bit alpha  | Used by pal4, pal8, BMP; supports full transparency |
| `-yuv422`| YUV422            | Lossy format with higher perceived color gamut  |
| `-bump`  | RGB Normal map    | Height map converted to SR                      |
| `-555`   | RGB PCX converter | **WARNING**: Use 1555 mode instead              |
| `-yuv420`| YUV420 converter  | **WARNING**: Used by YUV converter or .SAN files|
| `-p4bpp` | 4-bpp placeholder | **WARNING**: Color format in palette file       |
| `-p8bpp` | 8-bpp placeholder | **WARNING**: Color format in palette file       |

---

### <texture_format>
**Note**: Twiddled offers fast performance and high-fidelity colors on hardware.

| PARAM   | TEXTURE TYPE    | TWIDDLED  | DESCRIPTION                             | MIPMAPS |
| ------- | --------------- | --------- | --------------------------------------- | ------- |
| `-tw`    | Square          | Twiddled  | Square dimensions only                  | YES     |
| `-twre`  | Rectangle       | Twiddled  | Length, width multiples                 | NO      |
| `-re`    | Rectangle       | Not Twiddled | Length, width multiples               | NO      |
| `-st`    | Stride          | Not Twiddled | Width multiple of 32 (32-992)         | NO      |
| `-twal`  | Alias           | Twiddled  | Square dims. and Mips <= 8x8            | YES     |
| `-pal4`  | 16-colors palette | Twiddled | Square dimensions only                  | YES     |
| `-pal8`  | 256-colors palette | Twiddled | Square dimensions only                  | YES     |
| `-vq`    | Vector Quantized | Twiddled | Square dimensions only                  | YES     |
| `-svq`   | Small VQ        | Twiddled  | Square dimensions <= 64x64              | YES     |
| `-bmp`   | Bitmap          | Not Twiddled | Square dimensions only                 | YES     |

---

### <other options>
- `-mm`: Generate Mipmaps
- `-flip`: Vertical image flip
- `-cla`: Clean unused RGB from alpha channel
- `-gi <n>`: Specify GBIX header value
- `-gitrim`: Short GBIX header, saves 4 bytes
- `-pvptrim`: Remove unused colors of a 16 or 256 palette
- `-pvpbank <n>`: Specify PVP palette bank number from 0-63
- `-nopvp`: Do not create PVP file
- `-vqa1`: VQ Algo 1 - better for details, slower encoding speed for large images
- `-vqa2`: VQ Algo 2 - better for gradients, fast faiss algo
- `-vqi <n>`: VQ iterations: 10 is default value, increase for sharper details
- `-vqs <n>|rand`: VQ random seed: value or "rand", changing it will alter compression artifacts

---

## 5. EXAMPLES

### Convert PVR to Image
#### Example 1
Convert a PVR to default image format `.png`:
```bash
pypvr.exe "file1.PVR"
```

#### Example 2
Convert all `.PVR` files to images, save in `c:\images`, create log file for reimport:
```bash
pypvr.exe "*.pvr" -o "c:\images" -log
```

#### Example 3
Convert a `.PVR` to image, Vertical flip, save in `c:\decoded` directory:
```bash
pypvr.exe "infile1.PVR" -png -flip -o "c:\decoded"
```

### Convert Image to PVR
#### Example 1
Convert image to `.PVR`, default settings:
```bash
pypvr.exe "test.png"
```

#### Example 2
Automatically re-encode all images back to `.PVR` as per `pvr_log.txt`:
```bash
pypvr.exe "c:\image_dir\pvr_log.txt"
```

#### Example 3
Convert all `.png` images to `.PVR`, save them to output folder `c:\pvr_dir`:
```bash
pypvr.exe "*.png" -o "c:\pvr_dir"
```

#### Example 4
Convert image to 1555 twiddled, use Global Index 0:
```bash
pypvr.exe "test.png" -1555 -tw -gi 0
```

#### Example 5
Convert image to 565, VQ compress:
```bash
pypvr.exe "test.png" -565 -vq
```

### Binary Container Extraction
#### Example 1
Scan a binary file for `.PVR` / `.PVP` data:
```bash
pypvr.exe "unknown.DAT"
```

### Binary Container Rebuild
#### Example 1
Reimport modified images and palettes back to container using log file:
```bash
pypvr.exe "c:\myfolder\"pvr_log.txt"
```
