@echo off
echo Installing requirements...
pip install -r uploader/requirements.txt

echo Building executable...
cd uploader
pyinstaller --clean ^
    --noconsole ^
    --add-data "../image;image" ^
    --icon="../image/app_logo.ico" ^
    --name="P3_OTA_Updater" ^
    app.py

echo Build complete!
pause 