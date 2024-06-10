from pathlib import Path
import math

import anvil.server as server  # pip install anvil-server

import plotly.graph_objects as go  # pip install plotly
import plotly.express as px
from plotly.subplots import make_subplots

from merging import get_merged_df


DATA_DIR = Path.cwd()  # is recursive, subdirectories are also searched for correct .csv files automatically


def get_csv(filename_snippet: str) -> Path:
    files = list(DATA_DIR.rglob(f'{filename_snippet}*.csv'))
    if files:
        return files[0]
    else:
        raise FileNotFoundError(f'No .csv file found containing "{filename_snippet}"')


df = get_merged_df(
        DATA_DIR,
        get_csv('Regionale_kerncijfers_'), get_csv('primary_education_'), get_csv('georef'), get_csv('enrollment-secondary'),
        get_csv('Laag_en_langdurig_laag_inkomen_'),
        only_full_data=True,
)
df.reset_index(inplace=True)
df['Year'] = df['Year'].astype(str)
df.set_index(['Year', 'Gemeenten'], inplace=True)


@server.callable
def get_merged_data():
    dic = df.groupby(level=0).apply(lambda df: df.xs(df.name).to_dict()).to_dict()
    return dic


@server.callable
def get_cities():
    return sorted(df.index.get_level_values('Gemeenten').unique().to_list())


@server.callable
def get_fig(chosen_city, chosen_line, chosen_bar):
    df_dic = get_merged_data()

    years = [int(year) for year in df_dic.keys()]

    cities_data = {}

    for year, cols in df_dic.items():
        for col, cities_dic in cols.items():
            for city, val in cities_dic.items():
                dic = cities_data.get(city, {})
                lst = dic.get(col, [])
                lst.append(0 if math.isnan(val) else val)
                dic[col] = lst
                cities_data[city] = dic

    bars = [go.Bar(x=years, y=cols[chosen_bar], name=f'{chosen_bar}', yaxis='y1') for city, cols in
            cities_data.items() if city == chosen_city]
    lines = [go.Scatter(x=years, y=cols[chosen_line], name=f'{chosen_line}', yaxis='y2') for city, cols in
             cities_data.items() if city == chosen_city]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    for bar in bars:
        fig.add_trace(bar, secondary_y=False)
    for line in lines:
        fig.add_trace(line, secondary_y=True)

    fig.update_yaxes(title_text=chosen_bar, secondary_y=False)
    fig.update_yaxes(title_text=chosen_line, secondary_y=True)

    fig.layout.title = chosen_city

    return fig


if __name__ == '__main__':
    server.connect('server_FK6NDYOYR5NWJ7DVESPYU3A5-LB53SYJBDCL77PNP')  # pls don't leak my key
    server.wait_forever()
