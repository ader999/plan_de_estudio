from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import os
from pathlib import Path


class Command(BaseCommand):
    help = 'Upload Excel templates to Minio storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force upload even if file already exists in storage',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be uploaded without actually uploading',
        )

    def handle(self, *args, **options):
        # Path to local excel_templates directory
        templates_dir = Path(settings.BASE_DIR) / 'excel_templates'
        
        if not templates_dir.exists():
            raise CommandError(f'Templates directory not found: {templates_dir}')

        # Find all Excel files in the templates directory
        excel_files = list(templates_dir.glob('*.xlsx')) + list(templates_dir.glob('*.xls'))
        
        if not excel_files:
            self.stdout.write(self.style.WARNING('No Excel files found in excel_templates directory'))
            return

        self.stdout.write(f'Found {len(excel_files)} Excel template(s) to upload:')
        
        for excel_file in excel_files:
            self.stdout.write(f'  - {excel_file.name}')

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('Dry run complete. No files were uploaded.'))
            return

        # Upload each file
        uploaded_count = 0
        skipped_count = 0
        
        for excel_file in excel_files:
            # Storage path (keeping the same structure)
            storage_path = f'excel_templates/{excel_file.name}'
            
            # Check if file already exists
            if default_storage.exists(storage_path) and not options['force']:
                self.stdout.write(
                    self.style.WARNING(f'Skipping {excel_file.name} (already exists, use --force to overwrite)')
                )
                skipped_count += 1
                continue

            try:
                # Read local file
                with open(excel_file, 'rb') as f:
                    file_content = f.read()

                # Upload to storage
                content_file = ContentFile(file_content)
                saved_name = default_storage.save(storage_path, content_file)
                
                # Verify upload
                if default_storage.exists(saved_name):
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Uploaded {excel_file.name} -> {saved_name}')
                    )
                    uploaded_count += 1
                else:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Failed to verify upload of {excel_file.name}')
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error uploading {excel_file.name}: {str(e)}')
                )

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nUpload complete: {uploaded_count} uploaded, {skipped_count} skipped'
            )
        )

        # Show how to access files
        if uploaded_count > 0:
            self.stdout.write('\nFiles uploaded to Minio storage. Update your code to use:')
            self.stdout.write('from django.core.files.storage import default_storage')
            for excel_file in excel_files:
                storage_path = f'excel_templates/{excel_file.name}'
                self.stdout.write(f"template_file = default_storage.open('{storage_path}')")