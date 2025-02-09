<p align="center">
  <img src="https://github.com/user-attachments/assets/187425e7-e73a-4b8c-801b-ee2126db0e30">
</p>

# PyPVR - Unofficial PVR Image Tool

`PyPVR` is a modern tool written in Python for encoding / decoding PowerVR2 images used by `SEGA Dreamcast` and `SEGA Naomi`.
All texture modes, pixel formats, palettes and PVR variations used by SEGA's SDK are supported.

Originally made for Blender [NaomiLib addon](https://github.com/NaomiMod/blender-NaomiLib), `PyPVR` is now a standalone tool designed for beginners / experienced modders.<p></p>
Click on [Drag & Drop](#pypvr-drag--drop---quick-steps) or [Command Line](#pypvr-command-line-tool---table-of-contents) for usage examples.

`PyPVR` can be also used by developers for [Batch Encoding](#batch-encoding) or Python import for [buffer input/output](#python-buffer).

## Main Features
- Pyhon 3.9.12+, OS free!  ( Modules: numpy, PIL, faiss )
- Portable Windows application
- Drag & drop interface
- Command line tool
- Binary container (`.afs` `.bin` `.dat` `.pvm` `.tex`) extract / reimport 
- 2 VQ quality algorithms
- Palette color index preserved during conversion
- YUV420 encoding, Bump map

## ♥ Support ♥
- https://ko-fi.com/vincentnl
- https://patreon.com/vincentnl

## Credits

 - Rob2d for K-means idea leading to quality VQ encoding
 - Egregiousguy for YUV420 decoding 
 - Kion for SmallVQ mipmaps data
 - tvspelsfreak for SR conversion to normal map
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
## PyPVR Drag & Drop - Quick Steps
## Step 1 - Extraction:
Drag files into `PyPVR` (container or `.PVR` / `.PVP`) 
![extract container](https://github.com/user-attachments/assets/5c48710f-72e4-4d84-9b15-e3156f55262b)
## Step 2 - Modify Images:
Use your preferred software (Photoshop or Gimp recommended)
![modify](https://github.com/user-attachments/assets/975dc05d-61f6-4e3b-925a-b196b3ccbb2a)
## Step 3 - Reimport:
Drag `pvr_log.txt` on `PyPVR`, for quick reimport of all images.
![reimport container](https://github.com/user-attachments/assets/07097951-8fc3-4dbe-817a-293474b743e7)

---

## PyPVR Command Line Tool - Table of Contents
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
- `-nolog`: Do not create `pvr_info.txt` for later re-import
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
Convert all `.PVR` files to images, save in `c:\images`:
```bash
pypvr.exe "*.pvr" -o "c:\images"
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
---



# Developers Useage
`PyPVR` can be used for batch images encoding, by creating a simple `pvr_log.txt` file, or as `bytesarray` input/output when called as Python import module.

---

## Batch Encoding
- `PyPVR` encoder accepts `.png`, `.gif`, `.bmp`, `.tga`, `.jpg`, `.tif` images.
If you want to create your own build chain, make a text file called `pvr_log.txt` and feed it to `PyPVR`

Example:

```bash
IMAGE FILE : C:\Image1.png
TARGET DIR : C:\PVR
ENC PARAMS : -vq -1555 -mm 
---------------
IMAGE FILE : C:\Image2.png
TARGET DIR : C:\PVR
ENC PARAMS : -pal8 -1555 -nopvp
---------------
IMAGE FILE : C:\Image3.png
TARGET DIR : C:\PVR
ENC PARAMS : -pal8 -1555 -nopvp
```
---

## Python buffer
If used as module import, `PyPVR` can provide `bytesarray` as input / output with `-buffer` option.

- Physical file as input, encode bytes array as buffer output:
```bash
Pypvr().Encode('c:\filename.png -buffer').get_pvr_buffer()
```
- PIL image object as input, encode bytes array as buffer output:
```bash
Pypvr().Encode('-buffer',image).get_pvr_buffer()
```
- Physical file's palette as input, convert to palette buffer output:
```bash
Pypvr().Encode('c:\filename.png -buffer').get_pvp_buffer()
```
- PIL Image object's palette as input, palette buffer output:
```bash
Pypvr().Encode('-buffer',image).get_pvp_buffer()
```
