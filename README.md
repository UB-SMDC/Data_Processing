# README: Dataset Metadata Processing

## 1. Overview

This workflow describes the collection, processing, and preparation of dataset metadata obtained from the **[SFB 1502 GeoNetwork Catalog](https://ubsmdc.sfb1502.de/geonetwork/srv/eng/catalog.search)**.

The objective is to organize and standardize metadata information, particularly dataset links, data providers, and data distributors, for further analysis and processing.

## 2. Metadata Collection

Metadata records were retrieved from the GeoNetwork catalog by filtering datasets according to two criteria:

- **Data type:** In-situ, Remote Sensing (RS), Simulated, and Other.
- **Dataset status:** Completed and Ongoing.

Based on these filters, seven CSV files containing dataset metadata were downloaded in (Path\metadata):

1. `metadata_Insitu_Compeleted.csv`
2. `metadata_Insitu_Ongoing.csv`
3. `metadata_RS_Compeleted.csv`
4. `metadata_RS_Ongoing.csv`
5. `metadata_Simulated_Compeleted.csv`
6. `metadata_Simulated_Ongoing.csv`
7. `metadata_Other_Compeleted.csv`


## 3. Metadata Processing

The Python script `process_metadata.py in (Path\metadata)` was executed separately for each of the seven CSV files.

The script performs the following operations:

### 3.1. Metadata Link Generation

A metadata API link is generated for each dataset using its unique identifier (UUID).

### 3.2. Dataset Link Separation

Multiple links stored in the `link` column and separated by `###` are split into individual columns to improve accessibility and organization.

### 3.3. Data Provider and Distributor Extraction

The script downloads the associated PDF metadata documents and extracts organization names from fields such as:

- `Data provider (Data center)`
- `Source / Provider`

Where available, the organizations are classified according to their roles, such as data provider, originator, manager, archiver, or distributor.

The extracted information is used to populate the `data Providers` and `data Distributor` columns.

## 4. Output Files

After processing, the updated metadata tables were saved in (Path\metadata\Modified xlsx) two formats:

- **CSV (`.csv`):** For further automated processing and data analysis.
- **Excel (`.xlsx`):** For manual inspection, validation, and editing.

Both formats are retained for subsequent processing steps.

## 5. F-UJI in (Path\F-UJI)
here we have 2 folders

- **"Geonetwork Metadata results": for fuji_package and results regarding metadata link FAIR assessment 
- **"Original Link Results" for fuji_package and results regarding metadata link FAIR assessment.

the FUJI_pakage runs with run_fuji.py using summary.csv. 
for creating summary.csv in each folder, we need to use two different py code to summeries all metadata in seven different files. to this end: 
create_summary_orginalLink.py to summeried the datasets with the main original link. the results will saved as Original-summary.csv
create_summary.py to summeried the datasets with the metadata link. the results will saved as summary.csv
with these two CSV files, run_fuji.py runs and the results will save in the results folder. 


