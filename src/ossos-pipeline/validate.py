#!python
# A script to do validation
__author__ = "David Rusk <drusk@uvic.ca>"

import argparse
import tempfile

from ossos.gui import tasks


def launch_app(task, working_directory, output_directory, dry_run, debug, name_filter=None, 
               user_name=None, skip_previous=False):
    # Put import here to avoid the delay loading them.  This allows quick
    # feedback when argparse can tell the arguments are invalid, and makes
    # getting help with the -h flag faster.
    from ossos.gui.app import create_application

    create_application(task, working_directory, output_directory,
                       dry_run=dry_run, debug=debug, name_filter=name_filter,
                       user_id=user_name, skip_previous=skip_previous)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=tasks.task_list,
                        help="The task to perform.")
    parser.add_argument("input",
                        help="The directory with files to be processed.")
    parser.add_argument("-o", "--output",
                        required=False,
                        default=tempfile.gettempdir(),
                        help="The directory where any local output files will "
                             "be placed.")
    parser.add_argument("--dry-run",
                        dest="dry_run",
                        action="store_true",
                        help="Do a dry run, where no results are sent to "
                             "VOSpace.")
    parser.add_argument("--debug",
                        action="store_true",
                        help="wx inspection tool will be launched.")
    parser.add_argument("--name-filter",
                        dest="name_filter",
                        help="A filter to apply to object names when loading from a directory.")
    parser.add_argument("--skip-previous", action="store_true",
                        dest="skip_previous",
                        help="Don't show me observation that are already in the input files, TRACKS only")
    parser.add_argument("--username", dest="username", help="Your CADC username")

    args = parser.parse_args()

    if args.dry_run and args.output == tempfile.gettempdir():
        # Don't use tempdir as default for dry runs, use the input directory
        output = args.input
    else:
        output = args.output


    launch_app(args.task, args.input, output, args.dry_run, args.debug, args.name_filter,
               args.username, args.skip_previous)


if __name__ == "__main__":
    main()
