import { Component, inject, input, output, signal } from '@angular/core';
import { MediaUploadSpec } from '../../../core/constants/media-upload-specs.const';
import { MediaUploadService } from '../../../core/services/media-upload.service';
import { randomTheatricalMessage } from '../../../core/utils/theatrical-messages.util';

@Component({
  selector: 'tava-file-upload',
  standalone: true,
  templateUrl: './tava-file-upload.component.html',
  styleUrl: './tava-file-upload.component.scss',
})
export class TavaFileUploadComponent {
  private readonly uploader = inject(MediaUploadService);

  readonly kind = input<'image' | 'video'>('image');
  readonly label = input('Subir archivo');
  readonly accept = input('image/jpeg,image/png,image/webp,image/gif');
  readonly specs = input<MediaUploadSpec | null>(null);

  readonly uploaded = output<string>();

  readonly uploading = signal(false);
  readonly uploadLine = signal('');
  readonly lastUrl = signal<string | null>(null);
  readonly previewUrl = signal<string | null>(null);

  onPick(ev: Event): void {
    const input = ev.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this.upload(file);
    input.value = '';
  }

  onDrop(ev: DragEvent): void {
    ev.preventDefault();
    const file = ev.dataTransfer?.files?.[0];
    if (file) this.upload(file);
  }

  private upload(file: File): void {
    this.uploading.set(true);
    this.uploadLine.set(randomTheatricalMessage('upload'));
    if (this.kind() === 'image') {
      this.previewUrl.set(URL.createObjectURL(file));
    }
    this.uploader.upload(file, this.kind()).subscribe({
      next: (res) => {
        this.uploading.set(false);
        this.lastUrl.set(res.url);
        this.uploaded.emit(res.url);
      },
      error: () => {
        this.uploading.set(false);
        this.previewUrl.set(null);
      },
    });
  }
}
