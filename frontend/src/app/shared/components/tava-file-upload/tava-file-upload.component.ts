import { Component, inject, input, output, signal } from '@angular/core';
import { MediaUploadService } from '../../../core/services/media-upload.service';

@Component({
  selector: 'tava-file-upload',
  standalone: true,
  template: `
    <div
      class="upload-zone"
      [class.upload-zone--busy]="uploading()"
      (dragover)="$event.preventDefault()"
      (drop)="onDrop($event)"
    >
      <input
        #fileInput
        type="file"
        class="upload-zone__input"
        [accept]="accept()"
        (change)="onPick($event)"
      />
      @if (previewUrl() && kind() === 'image') {
        <img [src]="previewUrl()!" alt="Vista previa" class="upload-zone__preview" />
      }
      <p class="upload-zone__label">{{ label() }}</p>
      <p class="upload-zone__hint">Arrastra aquí o haz clic · {{ kind() === 'video' ? 'MP4, WebM' : 'JPG, PNG, WebP' }}</p>
      @if (uploading()) {
        <span class="upload-zone__status">Subiendo…</span>
      }
      @if (lastUrl()) {
        <p class="upload-zone__done">✓ Archivo listo</p>
      }
    </div>
  `,
  styles: `
    .upload-zone {
      position: relative;
      border: 2px dashed rgba(201, 162, 39, 0.45);
      border-radius: var(--tava-radius);
      padding: 1.25rem;
      text-align: center;
      background: rgba(255, 255, 255, 0.7);
      cursor: pointer;
      transition: border-color var(--tava-transition), box-shadow var(--tava-transition);

      &:hover {
        border-color: var(--tava-gold);
        box-shadow: var(--tava-shadow-glow);
      }

      &--busy {
        opacity: 0.75;
        pointer-events: none;
      }

      &__input {
        position: absolute;
        inset: 0;
        opacity: 0;
        cursor: pointer;
      }

      &__preview {
        max-height: 120px;
        border-radius: 8px;
        margin-bottom: 0.75rem;
        object-fit: cover;
      }

      &__label {
        font-weight: 600;
        color: var(--tava-gold-glow);
        margin: 0 0 0.25rem;
      }

      &__hint,
      &__status,
      &__done {
        font-size: 0.8rem;
        color: var(--tava-cream-muted);
        margin: 0.2rem 0;
      }

      &__done {
        color: #2d6a4f;
        font-weight: 600;
      }
    }
  `,
})
export class TavaFileUploadComponent {
  private readonly uploader = inject(MediaUploadService);

  readonly kind = input<'image' | 'video'>('image');
  readonly label = input('Subir archivo');
  readonly accept = input('image/jpeg,image/png,image/webp,image/gif');

  readonly uploaded = output<string>();

  readonly uploading = signal(false);
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
