# YCB 011 Banana

This directory contains the textured `011_banana` object from the YCB Object
and Model Set. It is stored locally so the MuJoCo scene can run without a
network connection.

- Source: https://www.ycbbenchmarks.com/object-models/
- Download archive: https://ycb-benchmarks.s3.amazonaws.com/data/google/011_banana_google_16k.tgz
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)
- License text: https://creativecommons.org/licenses/by/4.0/
- Citation: B. Calli et al., "The YCB object and Model set: Towards common benchmarks for manipulation research," 2015.

Included files:

- `textured.obj`: 16k-triangle object mesh
- `textured.mtl`: original OBJ material definition
- `texture_map.png`: original color texture

The loader removes the OBJ `mtllib` directive in memory because MuJoCo uses
its own material definition. The source files themselves are preserved.
