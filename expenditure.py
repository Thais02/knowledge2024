import pandas as pd
from pathlib import Path
import re


def _get_expenses_year_df(path: Path, only_begroting: bool, only_total: bool) -> pd.DataFrame:
    year = re.match(r'Gemeenten_(\d{4})_', path.stem).group(1)  # regex the year from the filename
    df = pd.read_csv(path, skiprows=4, skipfooter=1, sep=';', engine='python')

    # rename the columns, drop the last header row, add a Year column
    df.rename(columns={'Unnamed: 0': 'Gemeenten', 'Unnamed: 1': 'Verslagsoort', 'Categorie': 'Taakveld/balanspost'},
              inplace=True)
    df.drop(0, inplace=True)
    df['Year'] = year

    # create a multi-index Year > City > Prediction/Actual > Category
    df.set_index(
        pd.MultiIndex.from_arrays([df['Year'], df['Gemeenten'], df['Verslagsoort'], df['Taakveld/balanspost']]),
        inplace=True)
    df.drop(['Year', 'Gemeenten', 'Verslagsoort', 'Taakveld/balanspost'], axis=1, inplace=True)

    # add a Total column
    df = df.apply(pd.to_numeric)
    df: pd.DataFrame  # the df.apply function returns type Any so this is to help the IDE
    df['Total'] = df.sum(axis=1, numeric_only=True)
    df.insert(0, 'Total', df.pop('Total'))

    # add a Total row for each index set (total for the 4.x expenses)
    totals = df.groupby(['Year', 'Gemeenten', 'Verslagsoort'])['Total'].sum().reset_index()
    totals['Taakveld/balanspost'] = '4.T TOTAL'
    totals.set_index(pd.MultiIndex.from_arrays(
        [totals['Year'], totals['Gemeenten'], totals['Verslagsoort'], totals['Taakveld/balanspost']]), inplace=True)

    df = pd.concat([df, totals])
    df.drop(['Year', 'Gemeenten', 'Verslagsoort', 'Taakveld/balanspost'], axis=1, inplace=True)

    if only_begroting:
        df = df[df.index.isin(['Begroting'], level=2)]
        df.set_index(df.index.droplevel(level=2), inplace=True)

    if only_total:
        df = df[df.index.isin(['4.T TOTAL'], level='Taakveld/balanspost')]
        df.set_index(df.index.droplevel(level='Taakveld/balanspost'), inplace=True)
        df = df[['Total']]

    return df.sort_index()


def get_expenses_df(search_dir: Path, only_begroting=False, only_total=False) -> pd.DataFrame:
    year_dfs = []

    for path in search_dir.rglob('Gemeenten_*.csv'):
        year_dfs.append(_get_expenses_year_df(path, only_begroting, only_total))

    df = pd.concat(year_dfs)
    return df.sort_index()


def plot_expenses(df: pd.DataFrame, kind='bar', subplots=False, only_show_begroting=False):
    df = df[df.index.isin(['4.T TOTAL'], level=3)]
    df.set_index(df.index.droplevel(level=3), inplace=True)

    if only_show_begroting:
        df = df[df.index.isin(['Begroting'], level=2)]
        df.set_index(df.index.droplevel(level=2), inplace=True)
        unstack_levels = 1
    else:
        unstack_levels = (1, 2)

    return df.unstack(level=unstack_levels).plot(y='Total', kind=kind, figsize=(15, 15), subplots=subplots, rot=0,
                                                 ylabel='x1000 €')
