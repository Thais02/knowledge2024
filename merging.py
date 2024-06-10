import pandas as pd
from pathlib import Path
import re
import matplotlib.pyplot as plt

from expenditure import get_expenses_df
from enrollment import get_enrollment_df, get_secondary_enrollment_df
from socioecon import get_poverty_df


def get_cities_inner(df: pd.DataFrame) -> list[str]:
    """
    Returns a list of all cities which appear in all datasources
    """
    df_inner = df.dropna(how='any')
    return df_inner.index.get_level_values('Gemeenten').unique()


def get_merged_df(
        expenses_search_dir: Path,
        enrollment_path: Path, primary_enrollment_path: Path, citycodes_path: Path,
        poverty_path: Path,
        only_full_data=False,

):
    expenses_df = get_expenses_df(expenses_search_dir, only_begroting=True, only_total=True)
    enrollment_df = get_enrollment_df(enrollment_path, primary_enrollment_path, citycodes_path)
    poverty_df = get_poverty_df(poverty_path, only_total=True)

    expenses_df.rename(columns={'Total': 'Education expenses'}, inplace=True)
    enrollment_df.rename(columns={'Total': 'Total enrollment'}, inplace=True)
    poverty_df.rename(columns={'Minderjarige kinderen': 'Impoverished children'}, inplace=True)

    df = pd.merge(enrollment_df, expenses_df, on=['Year', 'Gemeenten'], how='outer')
    df = pd.merge(df, poverty_df, on=['Year', 'Gemeenten'], how='outer')

    if only_full_data:
        df.dropna(how='any', inplace=True)

    return df


def plot_merged_df(df: pd.DataFrame, cities: list[str]):
    for city in df.index.get_level_values('Gemeenten').unique():
        if city in cities:
            df_city = df.xs(city, level='Gemeenten')
            fig, ax1 = plt.subplots()

            df_city.plot(y=['Primary', 'Secondary', 'MBO Total', 'HBO', 'WO'],
                               kind='bar', title=f'Merged data {city}',
                               figsize=(10, 10), rot=0, ylabel='Students', ax=ax1)
            ax2 = ax1.twinx()
            df_city.plot(
                y=['Education expenses'],
                kind='line', title=f'Merged data {city}',
                figsize=(10, 10), rot=0, ylabel='Education expenses', ax=ax2)
            ax3 = ax2.twinx()
            df_city.plot(
                y=['Impoverished children'],
                kind='line', title=f'Merged data {city}',
                figsize=(10, 10), rot=0, ylabel='Impoverished children', ax=ax2)
            yield