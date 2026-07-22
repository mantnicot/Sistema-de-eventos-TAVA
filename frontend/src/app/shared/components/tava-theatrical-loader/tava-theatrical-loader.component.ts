import {
  AfterViewInit,
  Component,
  computed,
  effect,
  ElementRef,
  inject,
  Input,
  OnDestroy,
  OnInit,
  ViewChild,
  signal,
} from '@angular/core';
import { SiteSettingsService } from '../../../core/services/site-settings.service';
import { resolveMediaUrl } from '../../../core/utils/media-url.util';
import { randomTheatricalMessage } from '../../../core/utils/theatrical-messages.util';

@Component({
  selector: 'tava-theatrical-loader',
  standalone: true,
  templateUrl: './tava-theatrical-loader.component.html',
  styleUrl: './tava-theatrical-loader.component.scss',
})
export class TavaTheatricalLoaderComponent implements OnInit, AfterViewInit, OnDestroy {
  private readonly site = inject(SiteSettingsService);

  @Input() title = 'Preparando el escenario';
  @Input() context = 'loader';
  @ViewChild('loaderVideo') private videoRef?: ElementRef<HTMLVideoElement>;

  readonly currentMessage = signal('');
  readonly videoFailed = signal(false);

  readonly resolvedVideoSrc = computed(() => {
    const app = this.site.appearance();
    if (!app) return '';
    if (app && !app.loader_video_enabled) return '';
    const url = app?.loader_video_url?.trim();
    return url ? this.withCacheBuster(resolveMediaUrl(url)) : '';
  });

  private timer: ReturnType<typeof setInterval> | null = null;
  private playRetry: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    effect(() => {
      const src = this.resolvedVideoSrc();
      if (!src) {
        this.videoFailed.set(true);
        return;
      }
      this.videoFailed.set(false);
      queueMicrotask(() => this.playVideo());
    });
  }

  ngOnInit(): void {
    this.site.loadAppearance();
    this.rotate();
    this.timer = setInterval(() => this.rotate(), 3200);
  }

  ngAfterViewInit(): void {
    this.playVideo();
  }

  ngOnDestroy(): void {
    if (this.timer) clearInterval(this.timer);
    if (this.playRetry) clearTimeout(this.playRetry);
  }

  onVideoReady(): void {
    this.videoFailed.set(false);
    this.playVideo();
  }

  onVideoPlaying(): void {
    this.videoFailed.set(false);
  }

  onVideoError(): void {
    this.videoFailed.set(true);
  }

  private rotate(): void {
    this.currentMessage.set(randomTheatricalMessage(this.context));
  }

  private playVideo(): void {
    const video = this.videoRef?.nativeElement;
    if (!video || this.videoFailed() || !this.resolvedVideoSrc()) return;
    video.muted = true;
    video.loop = true;
    video.playsInline = true;
    const play = video.play();
    if (play) {
      void play.catch(() => {
        if (this.playRetry) clearTimeout(this.playRetry);
        this.playRetry = setTimeout(() => {
          if (!this.videoFailed() && video.paused) {
            void video.play().catch(() => undefined);
          }
        }, 400);
      });
    }
  }

  private withCacheBuster(src: string): string {
    if (src.startsWith('blob:') || src.startsWith('data:')) return src;
    const separator = src.includes('?') ? '&' : '?';
    return `${src}${separator}loader=${encodeURIComponent(src)}`;
  }
}
