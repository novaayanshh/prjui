def _luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    r, g, b = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    hi, lo = sorted([_luminance(hex_a), _luminance(hex_b)], reverse=True)
    return round((hi + 0.05) / (lo + 0.05), 2)
