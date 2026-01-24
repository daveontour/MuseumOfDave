from datetime import datetime
import json
import os
import subprocess
import sys

class ProcessImagesService:

    def find_imagemagick_command(self):
            """Find ImageMagick executable in system PATH.
            
            Returns:
                Path to ImageMagick executable or None if not found
            """
            # Try common ImageMagick command names
            commands = ["magick", "magick.exe", "convert"]
            
            # for cmd in commands:
            #     path = shutil.which(cmd)
            #     if path:
            #         return path
            
            # On Windows, also try common installation paths
        # if platform.system() == "Windows":
            common_paths = [
                r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe",
                r"C:\Program Files\ImageMagick-7.1.0-Q16-HDRI\magick.exe",
                r"C:\Program Files\ImageMagick-7.0.11-Q16-HDRI\magick.exe",
                r"C:\Program Files (x86)\ImageMagick-7.1.1-Q16-HDRI\magick.exe",
                r"C:\Program Files (x86)\ImageMagick-7.1.0-Q16-HDRI\magick.exe",
            ]
            for path in common_paths:
                if os.path.exists(path):
                    return path
            
            return None

    def parse_gps_coordinate(self,gps_string: str) -> float:
            """
            Parse GPS coordinate from ImageMagick format (degrees/minutes/seconds as fractions)
            to decimal degrees.
            
            Format: "degrees/numerator,minutes/numerator,seconds/numerator"
            Example: "25/1,6/1,4036/100" = 25° 6' 40.36"
            
            Args:
                gps_string: GPS coordinate string from ImageMagick
                
            Returns:
                Decimal degrees as float, or None if parsing fails
            """
            if not gps_string or gps_string.strip() == '':
                return None
            
            try:
                # Split by comma to get degrees, minutes, seconds
                parts = gps_string.split(',')
                if len(parts) != 3:
                    return None
                
                # Parse degrees: "25/1" -> 25.0
                deg_parts = parts[0].split('/')
                if len(deg_parts) == 2:
                    degrees = float(deg_parts[0]) / float(deg_parts[1])
                else:
                    degrees = float(deg_parts[0])
                
                # Parse minutes: "6/1" -> 6.0
                min_parts = parts[1].split('/')
                if len(min_parts) == 2:
                    minutes = float(min_parts[0]) / float(min_parts[1])
                else:
                    minutes = float(min_parts[0])
                
                # Parse seconds: "4036/100" -> 40.36
                sec_parts = parts[2].split('/')
                if len(sec_parts) == 2:
                    seconds = float(sec_parts[0]) / float(sec_parts[1])
                else:
                    seconds = float(sec_parts[0])
                
                # Convert DMS to decimal degrees
                decimal_degrees = degrees + (minutes / 60.0) + (seconds / 3600.0)
                return decimal_degrees
                
            except (ValueError, IndexError) as e:
                print(f"Warning: Could not parse GPS coordinate '{gps_string}': {e}")
                return None

    def parse_exif_data(self,exifJson):

        if exifJson.get('date_taken'):
            date_taken = datetime.strptime(exifJson['date_taken'], '%Y:%m:%d %H:%M:%S')
            exifJson['year'] = date_taken.year
            exifJson['month'] = date_taken.month
            exifJson['day'] = date_taken.day
        else:
            exifJson['year'] = None
            exifJson['month'] = None

        # Handle latitude - convert empty strings to None
        latitude_str = exifJson.get('latitude', '')
        if latitude_str and latitude_str.strip():
            latitude_decimal = self.parse_gps_coordinate(latitude_str)
            if latitude_decimal is not None:
                lat_ref = exifJson.get('latitude_ref', '').strip().upper()
                if lat_ref == 'S':
                    latitude_decimal = -latitude_decimal
                exifJson['latitude'] = latitude_decimal
            else:
                exifJson['latitude'] = None
        else:
            exifJson['latitude'] = None
            
        # Handle longitude - convert empty strings to None
        longitude_str = exifJson.get('longitude', '')
        if longitude_str and longitude_str.strip():
            longitude_decimal = self.parse_gps_coordinate(longitude_str)
            if longitude_decimal is not None:
                lon_ref = exifJson.get('longitude_ref', '').strip().upper()
                if lon_ref == 'W':
                    longitude_decimal = -longitude_decimal
                exifJson['longitude'] = longitude_decimal
            else:
                exifJson['longitude'] = None
        else:
            exifJson['longitude'] = None
            
        exifJson['has_gps'] = exifJson.get('latitude') is not None and exifJson.get('longitude') is not None

        return exifJson

    def create_thumb_and_get_exif(self,image_data: bytes, process_thunbnail: bool = True, process_exif: bool = True, width: int = 200):

        magick_cmd = self.find_imagemagick_command()
        format_string = '{"width": "%w", "height": "%h", "date_taken": "%[EXIF:DateTimeOriginal]", "latitude": "%[EXIF:GPSLatitude]", "longitude": "%[EXIF:GPSLongitude]", "latitude_ref": "%[EXIF:GPSLatitudeRef]", "longitude_ref": "%[EXIF:GPSLongitudeRef]", "title": "%[EXIF:DocumentName]", "description": "%[EXIF:ImageDescription]", "tags": "%[EXIF:Keywords]"}'


        if  process_thunbnail and process_exif:

            cmd = [
                        magick_cmd,
                        "-",
                        "-quiet",
                        "-format", format_string,
                        "-write", "info:fd:2",
                        "-filter", "Lanczos",
                        "-colorspace", "sRGB",
                        "-resize", f"{width}x{width}>",
                        "-unsharp", "0x0.75+0.75+0.008",
                        "-quality", "95",
                        "-strip",
                        "jpg:-",
                    ]

            try:
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                thumbnail, exif_data = process.communicate(input=image_data)

                if process.returncode != 0:
                        raise RuntimeError(f"ImageMagick Error: {exif_data.decode('utf-8')}")

                exifJson = json.loads(exif_data.decode('utf-8', errors='ignore'))
                exifJson = self.parse_exif_data(exifJson)

                return thumbnail, exifJson

            except Exception as e:
                print(f"Error: {e}")
                return None, None

        elif  process_thunbnail:
            cmd = [
                magick_cmd,
                "-",               # <--- Crucial: Tells Magick to read from STDIN
                "-filter", "Lanczos",
                "-colorspace", "sRGB",
                "-resize", f"{width}x{width}>",
                "-unsharp", "0x0.75+0.75+0.008",
                "-quality", "95",
                "-strip",
                "jpg:-"            # <--- Crucial: Force output format (jpg) to STDOUT
            ]

            try:
                # We pass the image_data to 'input='
                # We capture the result in 'stdout'
                process = subprocess.run(
                    cmd,
                    input=image_data,
                    capture_output=True,
                    check=True
                )
                return process.stdout, None
            except FileNotFoundError as e:
                error_msg = f"ImageMagick executable not found: {magick_cmd}. Error: {str(e)}"
                print(f"❌ {error_msg}")
                raise FileNotFoundError(error_msg)
            except subprocess.CalledProcessError as e:
                stderr_msg = e.stderr.decode() if e.stderr else "Unknown error"
                error_msg = f"ImageMagick Error: {stderr_msg}"
                print(f"❌ {error_msg}")
                return None, None
                
        elif process_exif:

                cmd = [
                    magick_cmd,
                    "identify",
                    "-quiet",
                    "-format", format_string,
                    "-"  # Read from stdin (must come after format specification)
                ]
                
                try:
                    # Pass bytes via stdin, decode stdout manually
                    process = subprocess.run(
                        cmd,
                        input=image_data,  # Pass bytes via stdin
                        capture_output=True,
                        check=True,
                        text=False  # Don't decode automatically since input is bytes
                    )
                    # Decode the output to string
                    if process.stdout:
                        data = process.stdout.decode('utf-8', errors='ignore')

                        exifJson = json.loads(data)
                        exifJson = self.parse_exif_data(exifJson)
                        return None, exifJson
                    return None, None
                except Exception as e:
                    print(f"Error: {e}")
                    if hasattr(e, 'stderr') and e.stderr:
                        print(f"Stderr: {e.stderr.decode('utf-8', errors='ignore')}")
                    return None, None

        else:
            return None, None