from pymagicc.definitions import (
    convert_magicc7_to_openscm_variables,
    convert_magicc_to_openscm_regions,
DATA_HIERARCHY_SEPARATOR,
DATTYPE_REGIONMODE_REGIONS
)
from .base import _Reader, _Writer
from datetime import datetime
import warnings

class _MAGReader(_Reader):
    def _get_column_headers_and_update_metadata(self, stream, metadata):
        column_headers, metadata = super()._get_column_headers_and_update_metadata(
            stream, metadata
        )
        column_headers = self._read_units(column_headers)

        return column_headers, metadata

class _MAGWriter(_Writer):
    def __init__(self, magicc_version=7):
        super().__init__(magicc_version=magicc_version)
        if self._magicc_version == 6:
            raise ValueError(".MAG files are not MAGICC6 compatible")

    def _get_header(self):
        try:
            header = self.minput.metadata.pop("header")
        except KeyError:
            warnings.warn(
                "No header detected, it will be automatically added. We recommend "
                "setting `self.metadata['header']` to ensure your files have the "
                "desired metadata."
            )
            from . import __version__

            header = "Date: {}\n" "Writer: pymagicc v{}".format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), __version__
            )

        mdata = self.minput.metadata
        sorted_keys = sorted(mdata.keys())
        metadata = "\n".join(
            [
                "{}: {}".format(k, mdata[k])
                for k in sorted_keys
                if k not in ["timeseriestype"]  # timeseriestype goes in namelist
            ]
        )

        return (
            "---- HEADER ----\n"
            "\n"
            "{}\n"
            "\n"
            "---- METADATA ----\n"
            "\n"
            "{}\n"
            "\n".format(header, metadata)
        )

    def _get_initial_nml_and_data_block(self):
        nml, data_block = super()._get_initial_nml_and_data_block()
        try:
            ttype = self.minput.metadata["timeseriestype"]
        except KeyError:
            raise KeyError(
                "Please specify your 'timeseriestype' in "
                "`self.metadata['timeseriestype'] before writing `.MAG` files"
            )

        nml["thisfile_specifications"]["thisfile_timeseriestype"] = ttype
        if ttype not in [
            "MONTHLY",
            "POINT_START_YEAR",
            "POINT_END_YEAR",
            "POINT_MID_YEAR",
            "AVERAGE_YEAR_START_YEAR",
            "AVERAGE_YEAR_MID_YEAR",
            "AVERAGE_YEAR_END_YEAR",
        ]:
            raise ValueError("Unrecognised timeseriestype: {}".format(ttype))

        data_timeseriestype_mismatch_error = ValueError(
            "timeseriestype ({}) doesn't match data".format(
                nml["thisfile_specifications"]["thisfile_timeseriestype"]
            )
        )
        its = self.minput.timeseries()

        if ttype in ("POINT_START_YEAR", "AVERAGE_YEAR_START_YEAR"):
            if not all([v.month == 1 and v.day == 1 for v in its.columns]):
                raise data_timeseriestype_mismatch_error

        elif ttype in ("POINT_MID_YEAR", "AVERAGE_YEAR_MID_YEAR"):
            if not all([v.month == 7 and v.day == 1 for v in its.columns]):
                raise data_timeseriestype_mismatch_error

        elif ttype in ("POINT_END_YEAR", "AVERAGE_YEAR_END_YEAR"):
            if not all([v.month == 12 and v.day == 31 for v in its.columns]):
                raise data_timeseriestype_mismatch_error

        elif ttype == "MONTHLY":
            # should either be weird timesteps or 12 months per year
            if nml["thisfile_specifications"]["thisfile_annualsteps"] not in (0, 12):
                raise data_timeseriestype_mismatch_error

        # don't bother writing this as it's in the header
        nml["thisfile_specifications"].pop("thisfile_units")

        return nml, data_block

    def _check_data_filename_variable_consistency(self, data_block):
        pass  # not relevant for .MAG files

    def _get_region_order(self, data_block):
        try:
            regions = data_block.columns.get_level_values("region").tolist()
            region_order_magicc = get_region_order(regions, self._scen_7)
            region_order = convert_magicc_to_openscm_regions(region_order_magicc)
            return region_order
        except ValueError:
            abbreviations = [
                convert_magicc_to_openscm_regions(r, inverse=True) for r in set(regions)
            ]
            unrecognised_regions = [
                a
                for a in abbreviations
                if a in regions or DATA_HIERARCHY_SEPARATOR in a
            ]
            if unrecognised_regions:
                warnings.warn(
                    "Not abbreviating regions, could not find abbreviation for {}".format(
                        unrecognised_regions
                    )
                )
            return regions

    def _get_dattype_regionmode(self, regions):
        try:
            rm = get_dattype_regionmode(regions, scen7=self._scen_7)[REGIONMODE_FLAG]
        except ValueError:
            # unrecognised regionmode so write NONE
            rm = "NONE"

        return {DATTYPE_FLAG: "MAG", REGIONMODE_FLAG: rm}