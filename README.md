# Transformer: Environment Logging to netCDF file

Loads Environment Logger files into a single netCDF file.

### Sample Docker Command Line

Below is a sample command line that shows how the Environment Logging to netCDF Docker image could be run.
An explanation of the command line options used follows.
Be sure to read up on the [docker run](https://docs.docker.com/engine/reference/run/) command line for more information.

The files used in this sample command line can be found on [Google Drive](https://drive.google.com/file/d/1NqvSz6PeuK2QWjSRcDhi1dbINFazSa11/view?usp=sharing).

```sh
docker run --rm --mount "src=/home/test,target=/mnt,type=bind" agpipeline/envlog2netcdf:2.0 --working_space "/mnt" "/mnt/2017-05-08"
```

This example command line assumes the source files are located in the `/home/test` folder of the local machine.
The name of the image to run is `agpipeline/envlog2netcdf:2.0`.

We are using the same folder for the source files and the output files.
By using multiple `--mount` options, the source and output files can be separated.

**Docker commands** \
Everything between 'docker' and the name of the image are docker commands.

- `run` indicates we want to run an image
- `--rm` automatically delete the image instance after it's run
- `--mount "src=/home/test,target=/mnt,type=bind"` mounts the `/home/test` folder to the `/mnt` folder of the running image

We mount the `/home/test` folder to the running image to make files available to the software in the image.

**Image's commands** \
The command line parameters after the image name are passed to the software inside the image.
Note that the paths provided are relative to the running image (see the --mount option specified above).

- `--working_space "/mnt"` specifies the folder to use as a workspace
- `"/mnt/2017-05-08"` is the name of the folder to look at for Environment Logger files. A combination of files and folders can be specified.