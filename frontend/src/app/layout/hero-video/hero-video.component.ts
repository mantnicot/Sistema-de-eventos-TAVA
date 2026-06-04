import { Component, ElementRef, inject, viewChild } from '@angular/core';
import { SiteSettingsService } from '../../core/services/site-settings.service';
import { resolveMediaUrl } from '../../core/utils/media-url.util';

@Component({
  selector: 'tava-hero-video',
  standalone: true,
  template: `
    @if (settings.appearance(); as app) {
      @if (app.hero_video_enabled && app.hero_video_url) {
        <div class="hero-video" aria-hidden="true">
          <video
            #bgVideo
            class="hero-video__media"
            [src]="videoSrc(app.hero_video_url)"
            autoplay
            muted
            loop
            playsinline
            preload="auto"
            (loadeddata)="onVideoReady()"
          ></video>
          <div class="hero-video__veil"></div>
        </div>
      }
    }
  `,
  styles: `
    .hero-video {
      position: fixed;
      inset: 0;
      z-index: 0;
      overflow: hidden;
      pointer-events: none;
    }
    .hero-video__media {
      width: 100%;
      height: 100%;
      object-fit: cover;
      filter: blur(14px) saturate(1.1) brightness(0.72);
      transform: scale(1.08);
    }
    .hero-video__veil {
      position: absolute;
      inset: 0;
      background: linear-gradient(
        180deg,
        rgba(250, 248, 244, 0.45) 0%,
        rgba(250, 248, 244, 0.62) 50%,
        rgba(250, 248, 244, 0.78) 100%
      );
    }
  `,
})
export class HeroVideoComponent {
  readonly settings = inject(SiteSettingsService);
  readonly videoSrc = resolveMediaUrl;
  private readonly videoRef = viewChild<ElementRef<HTMLVideoElement>>('bgVideo');

  onVideoReady(): void {
    const el = this.videoRef()?.nativeElement;
    if (!el) return;
    el.muted = true;
    el.volume = 0;
    el.play().catch(() => undefined);
  }
}
