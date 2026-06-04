import { Component, inject } from '@angular/core';
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
            class="hero-video__media"
            [src]="videoSrc(app.hero_video_url)"
            autoplay
            muted
            loop
            playsinline
            preload="metadata"
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
      z-index: -1;
      overflow: hidden;
      pointer-events: none;
    }
    .hero-video__media {
      width: 100%;
      height: 100%;
      object-fit: cover;
      filter: blur(28px) saturate(0.75) brightness(0.55);
      transform: scale(1.12);
    }
    .hero-video__veil {
      position: absolute;
      inset: 0;
      background: linear-gradient(
        180deg,
        rgba(255, 252, 248, 0.88) 0%,
        rgba(255, 252, 248, 0.94) 45%,
        rgba(255, 252, 248, 0.98) 100%
      );
    }
  `,
})
export class HeroVideoComponent {
  readonly settings = inject(SiteSettingsService);
  readonly videoSrc = resolveMediaUrl;
}
