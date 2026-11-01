"""Deterministic dependency-free CSS minification. JS ships directly as small modules."""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1] / 'hourly' / 'static'
css = root / 'app.css'
source = css.read_text()
source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
source = re.sub(r'\s+', ' ', source)
source = re.sub(r'\s*([{}:;,])\s*', r'\1', source)
css.write_text(source.strip()+'\n')
print('Compiled CSS:', css.stat().st_size, 'bytes')
print('JavaScript:', (root/'app.js').stat().st_size, 'bytes (unminified for debugging)')
