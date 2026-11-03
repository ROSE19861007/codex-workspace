"""Generate the crisp grid-and-floor-plan icon used by the local beta shortcut."""

from pathlib import Path

from PIL import Image, ImageDraw


SCALE = 4
SIZE = 256


def box(values):
    return tuple(round(value * SCALE) for value in values)


def main():
    output = Path(__file__).resolve().parent / "assets" / "space-editor-beta.ico"
    output.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Soft white app tile with the blue planning-grid base.
    draw.rounded_rectangle(box((10, 10, 246, 246)), radius=box((38,))[0], fill="#F8FBFF", outline="#B4C9DF", width=box((4,))[0])
    for position in range(34, 232, 25):
        draw.line((position * SCALE, 25 * SCALE, position * SCALE, 231 * SCALE), fill="#D5E4F1", width=2 * SCALE)
        draw.line((25 * SCALE, position * SCALE, 231 * SCALE, position * SCALE), fill="#D5E4F1", width=2 * SCALE)
    for position in (84, 159):
        draw.line((position * SCALE, 25 * SCALE, position * SCALE, 231 * SCALE), fill="#AEC8DE", width=3 * SCALE)
        draw.line((25 * SCALE, position * SCALE, 231 * SCALE, position * SCALE), fill="#AEC8DE", width=3 * SCALE)

    # Walls form a recognisable small plan, with two equipment blocks inside.
    wall = "#183D62"
    draw.rounded_rectangle(box((43, 49, 194, 68)), radius=box((5,))[0], fill=wall)
    draw.rounded_rectangle(box((43, 49, 62, 190)), radius=box((5,))[0], fill=wall)
    draw.rounded_rectangle(box((43, 171, 194, 190)), radius=box((5,))[0], fill=wall)
    draw.rounded_rectangle(box((175, 110, 194, 190)), radius=box((5,))[0], fill=wall)

    # Door gap plus the main equipment zones.
    draw.arc(box((151, 68, 199, 116)), start=180, end=270, fill="#527A9F", width=3 * SCALE)
    draw.line(box((175, 68, 175, 91)), fill="#527A9F", width=3 * SCALE)
    draw.rounded_rectangle(box((79, 89, 137, 139)), radius=box((8,))[0], fill="#2474B5", outline="#FFFFFF", width=box((4,))[0])
    draw.rounded_rectangle(box((92, 150, 151, 169)), radius=box((6,))[0], fill="#E5843D", outline="#FFFFFF", width=box((4,))[0])
    draw.rounded_rectangle(box((68, 102, 77, 126)), radius=box((4,))[0], fill="#5BA4D8")

    image = image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    image.save(output, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(output)


if __name__ == "__main__":
    main()
