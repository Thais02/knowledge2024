import pandas as pd
from pathlib import Path
import re


def get_enrollment_df(data_path: Path, primary_data_path: Path, citycodes_path: Path, secondary_path: Path,
                      only_total=False, split_vmbo=False) -> pd.DataFrame:
    df = pd.read_csv(data_path, skiprows=3, skipfooter=1, sep=';', engine='python', na_values='.')

    # rename the columns, drop the last header row, add a Year column
    df.rename(columns={
        'Unnamed: 0': 'Year',
        'Unnamed: 1': 'Gemeenten',
        'Onderwijs|Naar woongemeente|Leerlingen/studenten|Voortgezet onderwijs': 'Secondary',
        'Onderwijs|Naar woongemeente|Leerlingen/studenten|Beroepsopleidende leerweg': 'MBO1',
        'Onderwijs|Naar woongemeente|Leerlingen/studenten|Beroepsbegeleidende leerweg': 'MBO2',
        'Onderwijs|Naar woongemeente|Leerlingen/studenten|Hoger beroepsonderwijs': 'HBO',
        'Onderwijs|Naar woongemeente|Leerlingen/studenten|Wetenschappelijk onderwijs': 'WO',
    }, inplace=True)
    df.drop(0, inplace=True)

    df['Year'] = pd.to_numeric(df['Year'])

    df.drop('Secondary', axis=1, inplace=True)  # will be added later to not be included in total

    # add primary enrollment from different datasource
    primary_df = _get_primary_enrollment_df(primary_data_path, citycodes_path)
    primary_df.rename(columns={'AANTAL_LEERLINGEN': 'Primary'}, inplace=True)

    df = pd.merge(df, primary_df, on=['Year', 'Gemeenten'], how='outer')
    df.insert(0, 'Primary', df.pop('Primary'))

    # add granular secondary enrollment from different datasource
    secondary_df = _get_secondary_enrollment_df(secondary_path, split_vmbo=split_vmbo)

    df = pd.merge(df, secondary_df, on=['Year', 'Gemeenten'], how='outer')

    # create a multi-index Year > City
    df.set_index(pd.MultiIndex.from_arrays([df['Year'], df['Gemeenten']]), inplace=True)
    df.drop(['Year', 'Gemeenten'], axis=1, inplace=True)

    # add a Total column
    df = df.apply(pd.to_numeric)
    df: pd.DataFrame  # the df.apply function returns type Any so this is to help the IDE
    df['Total'] = df.sum(axis=1, numeric_only=True, min_count=1)
    df.insert(0, 'Total', df.pop('Total'))

    # sum both MBO variants, NOT included in total
    df['MBO Total'] = df['MBO1'] + df['MBO2']
    df.insert(4, 'MBO Total', df.pop('MBO Total'))

    # sum all secondary variants, NOT included in total
    df['Secondary'] = df['PRAKTIJK'] + df['VMBO'] + df['HAVO'] + df['VWO'] + df['HAVO/VWO']
    df.insert(1, 'Secondary', df.pop('Secondary'))

    if only_total:
        df = df[['Total']]
        df.dropna(inplace=True)

    return df.sort_index()


def _get_secondary_enrollment_df(path: Path, split_vmbo=False) -> pd.DataFrame:
    def extract_secondary_type(text: str) -> str:
        if text == 'Praktijkonderwijs alle vj':
            return 'PRAKTIJK'
        elif text in ('Brugjaar 1-2', 'HAVO/VWO lj 3'):
            return 'HAVO/VWO'
        else:
            match = re.match(r'^(\w{4}) ([A-Z]{2})', text)  # check for VMBO with added category
            if match:
                if split_vmbo:
                    return f'{match.group(1)} {match.group(2)}'
                else:
                    return match.group(1)

            match = re.match(r'^(\w{3,4}) [a-z]{2}',
                             text)  # check for HAVO or VWO, also captures "HAVO uitbesteed aan VAVO"
            if match:
                return match.group(1)

    df = pd.read_csv(path, sep=',', index_col='_id')

    df['PLAATSNAAM VESTIGING'] = df['PLAATSNAAM VESTIGING'].apply(str.capitalize)

    df.drop(['BEVOEGD GEZAG', 'NAAM BEVOEGD GEZAG', 'DENOMINATIE BG', 'BRIN NUMMER', 'VESTIGINGSNUMMER',
             'BRINVESTIGINGSNUMMER', 'DENOMINATIE VESTIGING', 'INSTELLINGSNAAM VESTIGING', 'PROVINCIE VESTIGING',
             'INDICATIE VO-VAVO', 'VMBO SECTOR', 'AFDELING'], axis=1, inplace=True)

    df['Type'] = df['ONDERWIJSTYPE VO EN LEER- OF VERBLIJFSJAAR'].apply(extract_secondary_type)

    df.rename(columns={'SCHOOLJAAR': 'Year', 'PLAATSNAAM VESTIGING': 'Gemeenten'}, inplace=True)

    df.loc[df['Gemeenten'] == 'Utrecht', 'Gemeenten'] = 'Utrecht (gemeente)'

    df.set_index(['Year', 'Gemeenten', 'LEERJAAR', 'Type'], inplace=True)
    df.drop(['ONDERWIJSTYPE VO EN LEER- OF VERBLIJFSJAAR'], axis=1, inplace=True)

    df = df.pivot_table(
        index=['Year', 'Gemeenten', 'LEERJAAR'],
        columns=['Type'],
        values='AANTAL LEERLINGEN',
        aggfunc='sum',
        fill_value=0
    )

    df = df.groupby(level=(0, 1)).sum()  # add level 2 to split by seniority year
    df: pd.DataFrame
    df.index.set_names(names='Gemeenten', level=1, inplace=True)
    df.sort_index(inplace=True)
    return df


def _get_primary_enrollment_df(data_path: Path, citycodes_path: Path) -> pd.DataFrame:
    def get_city_codes(path: Path) -> list[tuple[int, str]]:
        df = pd.read_csv(path, sep=';')
        df = df[['Gemeente code', 'Gemeente name']]
        df.loc[df['Gemeente name'] == 'Utrecht', 'Gemeente name'] = 'Utrecht (gemeente)'
        return list(df.itertuples(index=False, name=None))

    def process_city_data(df, city_code, city_name):
        # Filter the dataframe to include only rows where GEMEENTENUMMER matches the city_code
        city_df = df[df['GEMEENTENUMMER'] == city_code].copy()

        # Add a new column 'Plaatsnaam' with the city_name for the matching rows
        city_df.loc[:, 'Plaatsnaam'] = city_name

        # Replace -1 with 0 in 'AANTAL_LEERLINGEN' column
        city_df.loc[:, 'AANTAL_LEERLINGEN'] = city_df['AANTAL_LEERLINGEN'].replace(-1, 0)

        # Group the filtered data by 'PEILJAAR' and 'Plaatsnaam', summing the 'AANTAL_LEERLINGEN' for each year
        grouped_city_df = city_df.groupby(['PEILJAAR', 'Plaatsnaam']).agg({'AANTAL_LEERLINGEN': 'sum'}).reset_index()

        return grouped_city_df

    df = pd.read_csv(data_path)

    cities_dfs = []
    for city_code, city_name in get_city_codes(citycodes_path):
        cities_dfs.append(process_city_data(df, city_code, city_name))

    combined_df = pd.concat(cities_dfs).reset_index(drop=True)

    combined_df['PEILJAAR'] = pd.to_numeric(combined_df['PEILJAAR'])

    # Group the combined data by 'PEILJAAR' and 'Plaatsnaam', summing the 'AANTAL_LEERLINGEN' for each year
    multi_index_combined_df = combined_df.set_index(['PEILJAAR', 'Plaatsnaam']).sort_index()

    # Rename the index levels
    multi_index_combined_df.index.rename(['Year', 'Gemeenten'], inplace=True)

    return multi_index_combined_df


def plot_enrollment_city(df: pd.DataFrame, cities: list[str], kind='bar', subplots=False):
    for city in df.index.get_level_values('Gemeenten').unique():
        if city in cities:
            df_city = df.xs(city, level='Gemeenten')
            yield df_city.plot(y=['Primary', 'Secondary', 'MBO Total', 'HBO', 'WO'], kind=kind,
                               title=f'Enrollment {city}',
                               figsize=(10, 10), subplots=subplots, rot=0, ylabel='Students')


def plot_enrollment_total(df: pd.DataFrame, cities: list[str], kind='bar', subplots=False):
    df = df[df.index.isin(cities, level='Gemeenten')]
    return df.unstack(level=1).plot(y='Total', kind=kind, title='Total enrollment', figsize=(10, 10), subplots=subplots,
                                    rot=0,
                                    ylabel='Students')
