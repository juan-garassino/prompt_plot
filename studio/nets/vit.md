# ViT — PATCH PARTITIONING
**Essence:** a Vision Transformer breaks a 2D image into patches, flattens them
into a token sequence, then attends over all tokens at once. **Status:** to build.
(The QKᵀV attention core is covered by `transformer.md`; this is the ViT front-end.)

## The idea
A flat image grid is fractured into discrete patch tiles; each tile is projected
into a 1D token embedding; the sequence is fed to self-attention that connects
every token to every other. Locality is destroyed and re-learned via attention.

## Pen-plotter visual (our engine)
- Bottom: a flat iso image grid **fractured into 16 tiles**.
- **Red dashed** projection lines yank the tiles up/diagonally, flattening them
  into a horizontal row of 1D token bars.
- Above: a dense black **all-to-all web** (self-attention) over the tokens.

## Palette
black = tiles + attention web; red = the patch→sequence projection; cream paper.

## Annotations
`x∈R^{H×W×C} → x_p∈R^{N×(P²C)}`, `LINEAR PROJECTION`, `POSITIONAL ENCODING`.

## Reference prompt
Mechanical pen plotter, warm cream paper, isometric. Base: a flat intricate square
grid (Input Image) fractured into 16 discrete hovering tiles; red dashed projection
lines pull them up and diagonally, flattening into a single horizontal sequence of
1D geometric bars (token embeddings). Above, a dense obsessive black web connects
every token to every other (self-attention canopy). Red dashed 0.1mm projections
vs solid black tiles; the attention web nearly tears the paper. Annotations
`x_p∈R^{N×(P²C)}`, `PATCH PARTITIONING`, `POSITIONAL ENCODING`. No gradients.

## Build notes
Bespoke: iso image grid + tile lift transform (interpolate tile → row position);
attention web = `_poly` chords among token bars. Can pair with the transformer
topography piece as a two-panel ViT sheet.
