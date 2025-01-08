@echo off
echo Installing requirements...
pip install -r uploader/requirements.txt

echo Building executable...
cd uploader
pyinstaller --clean ^
    --noconsole ^
    --name="P3_OTA_Updater" ^
    gui.py

echo Build complete!
pause 