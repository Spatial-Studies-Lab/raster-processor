#### Use latest Ubuntu LTS release as the base
FROM ubuntu:bionic

ARG DEBIAN_FRONTEND=noninteractive

# Update base container install
RUN apt-get update
RUN apt-get upgrade -y

RUN apt-get install -y software-properties-common git
RUN add-apt-repository ppa:ubuntugis/ppa

# Install GDAL dependencies
RUN apt-get update
RUN apt-get install -y python3-pip libgdal-dev locales gdal-bin python-gdal

# Ensure locales configured correctly
RUN locale-gen en_US.UTF-8
ENV LC_ALL='en_US.utf8'

# Set python aliases for python3
RUN echo 'alias python=python3' >> ~/.bashrc
RUN echo 'alias pip=pip3' >> ~/.bashrc

# Update C env vars so compiler can find gdal
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV GDAL_DATA=/usr/share/gdal

# This will install latest version of GDAL
RUN pip3 install GDAL==2.2.3 rasterio boto3 cloudwatch sendgrid awscli

COPY . /

ENTRYPOINT [ "python3", "-u", "prep_rasters.py" ]