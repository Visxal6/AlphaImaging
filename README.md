# Alpha Imaging

Alpha Imaging is a lightweight desktop tool for working with image alpha channels during texture/modding workflows.

If you split an image’s alpha (transparency) into a separate mask while editing (e.g., in Krita) and later need to rebuild the original transparent texture, Alpha Imaging helps you do that quickly without manual channel work.

## What it does

- **Split**: Extract an image’s alpha channel into a separate grayscale mask
- **Combine**: Reapply a grayscale mask as the alpha channel to rebuild an RGBA texture
- **Validate**: Inspect alpha usage (missing, all-opaque, all-transparent, near-constant, etc.)
- **Generate**: Create alpha masks from luminance, thresholds, or color-keying

## Who it’s for

Texture and mesh modders who regularly move between editors and need a clean, repeatable way to preserve or reconstruct transparency.

## Download

Go to the **Releases** page and download the latest `AlphaImaging-Windows.zip`.

1. Unzip the file  
2. Run `AlphaImaging.exe`  

## Notes

- Windows may show a SmartScreen warning for unsigned apps. This is normal for small independent tools.
- This project is focused on alpha-channel workflows; it does not modify mesh geometry.

## License

See `LICENSE`.
