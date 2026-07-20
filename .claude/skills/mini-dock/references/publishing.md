# Publishing

Use this reference when packaging or uploading a Mini Dock app to the App Gallery.

Source:
- Publishing guide: https://dock.myvobot.com/developer/guides/publishing-guide/
- Application architecture: https://dock.myvobot.com/developer/guides/application-architecture/

## Publishing Flow

1. Create an app folder named after the app.
2. Include `__init__.py` and `manifest.yml`.
3. Add every file needed by the app to `manifest.yml`.
4. Run the official packaging tool for the user's platform.
5. Generate a `.vbt` file.
6. Log in to the App Gallery.
7. Create or select the app entry.
8. Upload the `.vbt` file with version information.
9. Wait for review. The official guide says review results are emailed within 15 working days.

## App Folder

Minimum publishing-oriented shape:

```text
your_app/
|-- manifest.yml
|-- __init__.py
`-- resources/
```

Larger apps may include:

```text
your_app/
|-- manifest.yml
|-- __init__.py
|-- app/
|-- resources/
`-- settings/
```

## manifest.yml

Example shape:

```yaml
application:
  name: MyApp
  version: 1.0.0
  description: This is a sample application for Mini Dock.
  author: John Doe
  author_email: developer@example.com
  bugs: https://github.com/example/myapp/issues
  repository: https://github.com/example/myapp
  licenses: MIT

system_requirements:
  minimum_version: 1.1.0
  compatible_devices:
    - MiniDock

files:
  include:
    - __init__.py
    - ui.py
    - resources/icon.png
```

Rules:
- Keep the file list complete; missing files will not be packaged.
- Keep app size under the official installed app limit of 200KB including resources.
- Keep all installed apps within the 900KB total app file-system limit.
- Use `resources/` for bundled files.

## Packaging Tool

The official guide provides packaging tool downloads for:
- macOS Apple Silicon
- macOS Intel
- Windows
- Linux x86_64

After selecting the app folder, the packaging tool generates a `.vbt` file.

## Upload

In the App Gallery:
1. Log in.
2. Open profile.
3. Create the app and fill app details.
4. Save.
5. Click Upload for the app.
6. Enter version information.
7. Select the `.vbt` file.
8. Save to finish upload.

The app is reviewed before publication.

