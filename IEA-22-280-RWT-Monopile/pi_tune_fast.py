import subprocess
from pyFAST.input_output import FASTOutputFile


# res = subprocess.run(
#     ['openfast_x64.exe', 'IEA-22-280-RWT-Monopile.fst'],
#     capture_output=True,
#     text=True,
# )


df = FASTOutputFile('IEA-22-280-RWT-Monopile.outb').toDataFrame()
print(df.head())