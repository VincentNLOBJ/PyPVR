<p align="center">
  <img src="https://github.com/user-attachments/assets/187425e7-e73a-4b8c-801b-ee2126db0e30">
</p>

# PyPVR - Python PVR Image Tool

`PyPVR` is an unofficial, modern tool written in Python for encoding / decoding PowerVR2 images used by `SEGA Dreamcast` and `SEGA Naomi`.

Originally made for Blender [NaomiLib addon](https://github.com/NaomiMod/blender-NaomiLib), `PyPVR` is now a standalone tool designed for beginners / experienced modders.<p></p>

- All texture modes, pixel formats, palettes and PVR variations used by SEGA's SDK are supported.

- Click on [Drag & Drop](#pypvr-drag--drop---quick-steps) or [Command Line](#pypvr-command-line-tool---table-of-contents) for usage examples.

- `PyPVR` can be also used by developers for [Batch Encoding](#batch-encoding) or Python import module for [Buffer Input/Output](#python-buffer).

Thanks to Rob2d for K-means idea, the 2 VQ compression algorithms can provide quality encoding results.

![PYPVR_VQMM](https://github.com/user-attachments/assets/fc5b2fcb-cebe-4c3e-b33b-89a7c3a0cc7d)


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
pypvr.py <infile1.PVR> -<options>
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
pypvr.py <infile> -<options>
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
pypvr.py "file1.PVR"
```

#### Example 2
Convert all `.PVR` files to images, save in `c:\images`:
```bash
pypvr.py "*.pvr" -o "c:\images"
```

#### Example 3
Convert a `.PVR` to image, Vertical flip, save in `c:\decoded` directory:
```bash
pypvr.py "infile1.PVR" -png -flip -o "c:\decoded"
```

### Convert Image to PVR
#### Example 1
Convert image to `.PVR`, default settings:
```bash
pypvr.py "test.png"
```

#### Example 2
Automatically re-encode all images back to `.PVR` as per `pvr_log.txt`:
```bash
pypvr.py "c:\image_dir\pvr_log.txt"
```

#### Example 3
Convert all `.png` images to `.PVR`, save them to output folder `c:\pvr_dir`:
```bash
pypvr.py "*.png" -o "c:\pvr_dir"
```

#### Example 4
Convert image to 1555 twiddled, use Global Index 0:
```bash
pypvr.py "test.png" -1555 -tw -gi 0
```

#### Example 5
Convert image to 565, VQ compress:
```bash
pypvr.py "test.png" -565 -vq
```

### Binary Container Extraction
#### Example 1
Scan a binary file for `.PVR` / `.PVP` data:
```bash
pypvr.py "unknown.DAT"
```

### Binary Container Rebuild
#### Example 1
Reimport modified images and palettes back to container using log file:
```bash
pypvr.py "c:\myfolder\"pvr_log.txt"
```
---



# Developers Usage
`PyPVR` can process batch encoding of multiple images, by creating a simple `pvr_log.txt` file.

Additionally, it can be used as an import module for encoding/decoding as `bytesarray` input/output.

---

## Batch Encoding
- `PyPVR` encoder accepts `.png`, `.gif`, `.bmp`, `.tga`, `.jpg`, `.tif` images.
If you want to create your own build chain, make a text file called `pvr_log.txt` and feed it to `PyPVR`

Example `pvr_log.txt`:

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

### Decode PVR --> Image buffer

- pvr buffer input, pvp buffer input, decode to image buffer output:

*Please note, internally it'll be converted into a .BMP with full alpha blending to simplify any further conversions.*
```bash
image_buffer = Pypvr.Decode('-buffer', buff_pvr = data , buff_pvp = palette ).get_image_buffer()
```
---
### Encode Image --> PVR / PVP buffer
- Image file as input, pvr buffer output, VQ compress:
```bash
pvr_buffer = Pypvr.Encode('c:\filename.png -buffer -vq').get_pvr_buffer()
```
- PIL image object as input, pvr buffer output:
```bash
pvr_buffer = Pypvr.Encode('-buffer',PILImage).get_pvr_buffer()
```
- Image as palette input, palette pvp buffer output:
```bash
pvp_buffer = Pypvr.Encode('c:\filename.png -buffer').get_pvp_buffer()
```
- PIL Image object's palette as input, palette pvp buffer output:
```bash
pvp_buffer = Pypvr.Encode('-buffer',PILImage).get_pvp_buffer()
```
