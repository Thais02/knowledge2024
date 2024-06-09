import pandas as pd
from pathlib import Path


def get_poverty_df(path: Path, only_total=False) -> pd.DataFrame:
    df = pd.read_csv(path, skiprows=4, skipfooter=1, sep=';', engine='python')

    # rename the columns, drop the last header row, add a Year column
    df.rename(columns={
        'Unnamed: 0': 'Year',
        'Unnamed: 1': 'Gemeenten',
        'Unnamed: 2': 'Inkomensgrens huishouden',
    }, inplace=True)
    df.drop(0, inplace=True)

    # create a multi-index Year > City > Category
    df.set_index(pd.MultiIndex.from_arrays([df['Year'], df['Gemeenten'], df['Inkomensgrens huishouden']]), inplace=True)
    df.drop(['Year', 'Gemeenten', 'Inkomensgrens huishouden'], axis=1, inplace=True)
    df.sort_index(inplace=True)

    if only_total:
        df = df.xs('Totaal', level='Inkomensgrens huishouden')
        df.drop(['Minderjarige kinderen relatief'], axis=1, inplace=True)

    return df
