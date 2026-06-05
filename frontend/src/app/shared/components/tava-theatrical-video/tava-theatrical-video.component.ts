import { Component, ElementRef, input, viewChild } from '@angular/core';

@Component({
  selector: 'tava-theatrical-video',
  standalone: true,
  templateUrl: './tava-theatrical-video.component.html',
  styleUrl: './tava-theatrical-video.component.scss',
})
export class TavaTheatricalVideoComponent {
  readonly src = input.required<string>();
  readonly poster = input<string | null>(null);
  readonly title = input('Trailer');

  private readonly videoRef = viewChild<ElementRef<HTMLVideoElement>>('video');
  private readonly progressRef = viewChild<ElementRef<HTMLInputElement>>('progress');
  playing = false;
  muted = false;

  togglePlay(): void {
    const el = this.videoRef()?.nativeElement;
    if (!el) return;
    if (el.paused) {
      void el.play();
      this.playing = true;
    } else {
      el.pause();
      this.playing = false;
    }
  }

  onPlay(): void {
    this.playing = true;
  }

  onPause(): void {
    this.playing = false;
  }

  toggleMute(): void {
    const el = this.videoRef()?.nativeElement;
    if (!el) return;
    el.muted = !el.muted;
    this.muted = el.muted;
  }

  seek(ev: Event): void {
    const input = ev.target as HTMLInputElement;
    const el = this.videoRef()?.nativeElement;
    if (!el || !input.value) return;
    el.currentTime = Number(input.value);
  }

  onTimeUpdate(): void {
    const el = this.videoRef()?.nativeElement;
    const bar = this.progressRef()?.nativeElement;
    if (!el || !bar) return;
    bar.max = String(el.duration || 0);
    bar.value = String(el.currentTime);
  }
}
