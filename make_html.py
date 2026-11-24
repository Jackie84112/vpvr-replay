import pathlib
t=pathlib.Path('template.html').read_text(encoding='utf-8')
d=pathlib.Path('data.json').read_text(encoding='utf-8')
pathlib.Path('index.html').write_text(t.replace('/*DATA*/',d),encoding='utf-8')
print('index.html', len(t)+len(d))
