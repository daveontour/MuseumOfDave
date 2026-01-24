from datetime import datetime


from src.services.process_images_service import ProcessImagesService

file_path = "C:\\NonOneDrive\\iCloud Sorted\\2025\\2025-01 January\\IMG_6801(1).HEIC"
file_path2 = "C:\\NonOneDrive\\iCloud Sorted\\2024\\2024-01 January\\1a946b89-85b2-417f-802a-cbdcb4dcd19c.JPG"



def main():
    with open(file_path, "rb") as f:
        image_data = f.read()
        process_images_service = ProcessImagesService()
        thumbnail, exif_data = process_images_service.create_thumb_and_get_exif(image_data, process_thunbnail=True, process_exif=True, width=1000)
        if thumbnail:
            with open("C:\\Users\\dave_\\OneDrive\\Desktop\\output_thumb.jpg", "wb") as f:
                f.write(thumbnail)
            print("Thumbnail saved successfully")
        else:
            print("No thumbnail created (process_thunbnail=False)")
        if exif_data:
            print("EXIF Data:")
            print(exif_data)
        else:
            print("No EXIF data extracted")


if __name__ == "__main__":
    main()