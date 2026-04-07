import PyInstaller.__main__
import os
import sys

def build():
    print("[IPAVERSE] Initiating Build Package creation...")
    setup_args = [
        'main.py',
        '--name', 'IpaVerse',
        '--noconsole', # No console window (silent)
        '--onefile',
        '--add-data', f'assets/textures{os.pathsep}assets/textures',
        '--add-data', f'history{os.pathsep}history',
    ]

    icon_path = 'assets/textures/presa.png'
    if os.path.exists(icon_path):
        setup_args.extend(['--icon', icon_path])

    PyInstaller.__main__.run(setup_args)
    print("[IPAVERSE] Build process complete!")

if __name__ == '__main__':
    build()
