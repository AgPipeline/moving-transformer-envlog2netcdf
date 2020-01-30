"""My nifty transformer
"""

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import shutil
import netCDF4

import environmental_logger_json2netcdf as ela

import configuration
import transformer_class

# Define the files we're looking for
ENVIRONMENT_LOGGING_FILENAME_END = '_environmentlogger.json'


class __internal__:
    """Class for functionality to only be used by this file"""
    def __init__(self):
        """Initializes class instance"""

    @staticmethod
    def get_environment_logging_files(file_folder_list: list) -> list:
        """Returns the list of found environment logging files
        Arguments:
            file_folder_list: the list of files and folders to look through
        Return:
            Returns a list of
        """
        found_files = []
        for one_name in file_folder_list:
            if os.path.isdir(one_name):
                for one_sub_name in os.listdir(one_name):
                    if one_sub_name.endswith(ENVIRONMENT_LOGGING_FILENAME_END):
                        found_files.append(os.path.join(one_name, one_sub_name))
            elif one_name.endswith(ENVIRONMENT_LOGGING_FILENAME_END):
                found_files.append(one_name)

        return found_files

    @staticmethod
    def produce_attr_dict(netcdf_variable_obj) -> list:
        """Produce a list of dictionary with attributes and value (Each dictionary is one data point)
        Arguments:
            netcdf_variable_obj: the object to convert to a dictionary
        Return:
            Returns a list of attributes as a dictionary
        """
        attributes = [attr for attr in dir(netcdf_variable_obj) if isinstance(attr, (str, bytes))]
        result = {name: getattr(netcdf_variable_obj, name) for name in attributes}

        return [dict(list(result.items()) + list({"value": str(data)}.items())) for data in netcdf_variable_obj[...]]


def add_parameters(parser: argparse.ArgumentParser) -> None:
    """Adds parameters
    Arguments:
        parser: instance of argparse.ArgumentParser
    """
    parser.add_argument('--batch_size', type=int, default=3000, help="max number of data points to submit at a time")
    parser.add_argument('--override_date', help="the date to use as part of the output file names")

    parser.epilog ="Processes one day's worth of data at a time"

    # Here we specify a default metadata file that we provide to get around the requirement while also allowing
    # pylint: disable=protected-access
    for action in parser._actions:
        if action.dest == 'metadata' and not action.default:
            action.default = ['/home/extractor/default_metadata.json']
            break


def perform_process(transformer: transformer_class.Transformer, check_md: dict) -> dict:
    """Performs the processing of the data
    Arguments:
        transformer: instance of transformer class
        check_md: request specific metadata
    Return:
        Returns a dictionary with the results of processing
    """
    # pylint: disable=unused-argument
    start_timestamp = datetime.datetime.now()
    total_files_folders = 0

    # Loop through and get the list of files
    days_files = __internal__.get_environment_logging_files(check_md['list_files']())
    if not days_files:
        msg = "Did not find environment logging files in list of files and folders specified"
        logging.error(msg)
        return {'code': -1000, 'error': msg}

    # Get the date stamp to use as part of the output file names
    datestamp, timestamp = None, None
    if 'timestamp' in check_md and check_md['timestamp']:
        # Use the timestamp as the basis for the output files
        # TODO: use Python3.7+ ISO timestamp handling functions
        timestamp = check_md['timestamp']
        datestamp = check_md['timestamp'][0:10]
    else:
        # Check the file name
        match = re.match('\\d{4}-\\d{2}-\\d{2}', os.path.basename(days_files[0]))
        if match:
            datestamp = match[0]
            timestamp = datestamp + 'T00:00:00'
    if transformer.args.override_date:
        timestamp = transformer.args.override_date + 'T00:00:00'
        datestamp = transformer.args.override_date
    if not datestamp or not timestamp:
        msg = "Unable to determine date to use as part of the output file names. Try the --override_date command line flag"
        logging.error(msg)
        return {'code': -1001, "error": msg}

    # Initialize local variables based upon the timestamp
    out_fullday_netcdf = os.path.join(check_md['working_folder'], datestamp + "_environment_logger.nc")
    temp_out_full = os.path.join(check_md['working_folder'], "temp_full.nc")
    temp_out_single = temp_out_full.replace("_full.nc", "_single.nc")
    geo_csv = out_fullday_netcdf.replace(".nc", "_geo.csv")

    for one_file in days_files:
        logging.info("Converting %s to netCDF & appending", os.path.basename(one_file))
        ela.mainProgramTrigger(one_file, temp_out_single)
        cmd = ['ncrcat', '--record_append', temp_out_single, temp_out_full]
        # Run without check since we don't know what the result will be
        # pylint: disable=subprocess-run-check
        logging.debug("Running command: %s", str(cmd))
        subprocess.run(cmd)
        os.remove(temp_out_single)

    shutil.move(temp_out_full, out_fullday_netcdf)

    # Write out geostreams CSV file
    logging.info("Creating geostreams CSV: '%s'", geo_csv)
    geo_file = open(geo_csv, 'w')
    geo_file.write(','.join(['site', 'trait', 'lat', 'lon', 'dp_time', 'source', 'value', 'timestamp']) + '\n')
    with netCDF4.Dataset(out_fullday_netcdf, 'r') as in_cdf:
        # Disable the following pylint check since I'm not sure why it's flagged
        # pylint: disable=consider-using-set-comprehension
        streams = set([sensor_info.name for sensor_info in in_cdf.variables.values() if sensor_info.name.startswith('sensor')])
        for stream in streams:
            if stream == 'sensor_spectrum':
                continue
            try:
                member_list = in_cdf.get_variables_by_attributes(sensor=stream)
                for members in member_list:
                    data_points = __internal__.produce_attr_dict(members)
                    for index, dp_obj in enumerate(data_points):
                        if dp_obj["sensor"] == stream:
                            time_format = "%Y-%m-%dT%H:%M:%S-07:00"
                            time_point = (datetime.datetime(year=1970, month=1, day=1) + \
                                          datetime.timedelta(days=in_cdf.variables["time"][index])).strftime(time_format)

                            geo_file.write(','.join(["Full Field - Environmental Logger",
                                                     "(EL) %s" % stream,
                                                     str(33.075576),
                                                     str(-111.974304),
                                                     time_point,
                                                     out_fullday_netcdf,
                                                     '"%s"' % json.dumps(dp_obj).replace('"', '""'),
                                                     timestamp]) + '\n')

            except Exception:
                logging.warning("NetCDF attribute not found and is being skipped: '%s'" % str(stream))

    file_md = [
        {
            'path': out_fullday_netcdf,
            'key': configuration.TRANSFORMER_SENSOR
        }, {
            'path': geo_csv,
            'key': 'csv'
        }]

    return {
        'code': 0,
        'file': file_md,
        configuration.TRANSFORMER_NAME: {
            'version': configuration.TRANSFORMER_VERSION,
            'utc_timestamp': datetime.datetime.utcnow().isoformat(),
            'processing_time': str(datetime.datetime.now() - start_timestamp),
            'num_files_dirs_received': str(total_files_folders),
            'num_environment_files': str(len(days_files)),
            'source_files': str(days_files).strip('[]')
        }
    }
