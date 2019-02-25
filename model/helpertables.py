"""Helper Tables module.

Provides adoption data for use in the other modules. The source of the adoption
data is selectable according to the solution. Helper Tables can pull in one of
the Linear/2nd order poly/3rd order poly/etc curve fitting implementations
from interpolation.py, or use a simple linear fit implemented here.
"""
from functools import lru_cache
import numpy as np
import pandas as pd


class HelperTables:
    """ Implementation for the Helper Tables module. """

    def __init__(self, ac, adoption_data_per_region, ref_datapoints, pds_datapoints, ref_tam_per_region=None,
                 pds_tam_per_region=None, adoption_trend_per_region=None, adoption_is_single_source=False):
        """
        HelperTables.
           Arguments:
             ac = advanced_controls.py object, storing settings to control
               model operation.
             adoption_data_per_region: dataframe with one column per region (World, OECD90, Eastern
               Europe, Latin America, etc).
             ref_datapoints: a DataFrame with columns per region and two rows for two years of data.
             pds_datapoints: a DataFrame with columns per region and two rows for two years of data.
             ref_tam_per_region: dataframe of total addressable market per major
               region for the Reference scenario.
             pds_tam_per_region: dataframe of total addressable market per major
               region for the PDS scenario.
             adoption_trend_per_region: adoption trend (predictions using 2nd Poly, 3rd Poly, etc
               as configured in the solution) with one column per region
             adoption_is_single_source (bool): whether the adoption data comes from a single source
               or multiple, to determine how to handle stddev.
        """
        self.ac = ac
        self.ref_datapoints = ref_datapoints
        self.pds_datapoints = pds_datapoints
        self.ref_tam_per_region = ref_tam_per_region
        self.pds_tam_per_region = pds_tam_per_region
        self.adoption_data_per_region = adoption_data_per_region
        self.adoption_trend_per_region = adoption_trend_per_region
        self.adoption_is_single_source = adoption_is_single_source

    @lru_cache()
    def soln_ref_funits_adopted(self, suppress_override=False):
        """Cumulative Adoption in funits, interpolated between two ref_datapoints.

           Arguments:
             suppress_override: disable ref_adoption_use_pds_years processing. This is
               used to avoid an infinite loop if both pds_adoption_use_ref_years and
               ref_adoption_use_pds_years are set.

           SolarPVUtil 'Helper Tables'!B26:L73
        """

        first_year = self.ref_datapoints.first_valid_index()
        last_year = 2060
        adoption = pd.DataFrame(0, index=np.arange(first_year, last_year + 1),
                                columns=self.ref_datapoints.columns.copy(), dtype='float')
        adoption = self._linear_forecast(first_year, last_year, self.ref_datapoints, adoption)

        if self.ac.soln_ref_adoption_regional_data:
            adoption.loc[:, "World"] = 0
            adoption.loc[:, "World"] = adoption.sum(axis=1)

        # cannot exceed tam
        if self.ref_tam_per_region is not None:
            for col in adoption.columns:
                adoption[col] = adoption[col].combine(self.ref_tam_per_region[col], min)

        if not suppress_override and self.ac.ref_adoption_use_pds_years:
            y = self.ac.ref_adoption_use_pds_years
            adoption.update(self.soln_pds_funits_adopted(suppress_override=True).loc[y, 'World'])

        adoption.name = "soln_ref_funits_adopted"
        adoption.index.name = "Year"
        return adoption

    def _linear_forecast(self, first_year, last_year, datapoints, adoption):
        """Interpolates a line between datapoints, and fills in adoption.
           first_year: an integer, the first year to interpolate data for.
           last_year: an integer, the last year to interpolate data for.
           datapoints: a Pandas DataFrame with two rows of adoption data, indexed by year.
             The columns are expected to be regions like 'World', 'EU', 'India', etc.
             There can be as many columns as desired, but the columns in datapoints
             must match the columns in adoption.
             The year+adoption data provide the X,Y coordinates for a line to interpolate.
           adoption: a Pandas DataFrame with columns which match the columns in datapoints.
             One row per year between first_year and last_year will be filled in, using
             adoption data interpolated from the line formed by the datapoints argument.
        """
        year1 = datapoints.index.values[0]
        year2 = datapoints.index.values[1]

        for col in adoption.columns:
            adopt1 = datapoints.loc[year1, col]
            adopt2 = datapoints.loc[year2, col]
            for year in range(first_year, last_year + 1):
                fract_year = (float(year) - float(year1)) / (float(year2) - float(year1))
                fract_adopt = fract_year * (float(adopt2) - float(adopt1))
                adoption.loc[year, col] = adopt1 + fract_adopt
        return adoption

    @lru_cache()
    def soln_pds_funits_adopted(self, suppress_override=False):
        """Cumulative Adoption in funits in the PDS.

           Arguments:
             suppress_override: disable pds_adoption_use_ref_years processing. This is
               used to avoid an infinite loop if both pds_adoption_use_ref_years and
               ref_adoption_use_pds_years are set.

           SolarPVUtil 'Helper Tables'!B90:L137
        """
        if self.ac.soln_pds_adoption_basis == 'Fully Customized PDS':
            year_2014_loc = self.adoption_data_per_region.index.get_loc(2014)
            adoption = self.adoption_data_per_region.iloc[year_2014_loc:, :].copy(deep=True)
        else:
            first_year = self.pds_datapoints.first_valid_index()
            last_year = 2060
            adoption = pd.DataFrame(0, index=np.arange(first_year, last_year + 1),
                                    columns=self.pds_datapoints.columns.copy(), dtype='float')

            if self.ac.soln_pds_adoption_basis == 'Linear':
                adoption = self._linear_forecast(first_year, last_year, self.pds_datapoints, adoption)
            elif self.ac.soln_pds_adoption_basis == 'S-Curve':
                raise NotImplementedError('S-Curve support not implemented')
            elif self.ac.soln_pds_adoption_basis == 'Existing Adoption Prognostications':
                adoption = self.adoption_trend_per_region.fillna(0.0)
            elif self.ac.soln_pds_adoption_basis == 'Customized S-Curve Adoption':
                raise NotImplementedError('Custom S-Curve support not implemented')

            if self.adoption_is_single_source:
                # The World region can specify a single source (all the sub-regions use
                # ALL SOURCES). If it does, use that one source without curve fitting.
                adoption['World'] = self.adoption_data_per_region.loc[first_year:, 'World']

            if self.ac.soln_pds_adoption_regional_data:
                adoption.loc[:, 'World'] = 0
                adoption.loc[:, 'World'] = adoption.sum(axis=1)

            # cannot exceed the total addressable market
            if self.pds_tam_per_region is not None:
                for col in adoption.columns:
                    adoption[col] = adoption[col].combine(self.pds_tam_per_region[col], min)

        if not suppress_override and self.ac.pds_adoption_use_ref_years:
            y = self.ac.pds_adoption_use_ref_years
            adoption.update(self.soln_ref_funits_adopted(suppress_override=True).loc[y, 'World'])

        # Where we have actual data, use the actual data not the interpolation.
        adoption.update(self.pds_datapoints.iloc[[0]])

        adoption.name = "soln_pds_funits_adopted"
        adoption.index.name = "Year"
        return adoption

    def to_dict(self):
        """Return all fields as a dict, to be serialized to JSON."""
        rs = dict()
        rs['soln_ref_funits_adopted'] = self.soln_ref_funits_adopted()
        rs['soln_pds_funits_adopted'] = self.soln_pds_funits_adopted()
        return rs
