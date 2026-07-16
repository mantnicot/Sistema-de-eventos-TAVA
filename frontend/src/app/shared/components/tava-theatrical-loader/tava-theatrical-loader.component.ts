import { AfterViewInit, Component, ElementRef, Input, OnDestroy, OnInit, ViewChild, signal } from '@angular/core';
import { randomTheatricalMessage } from '../../../core/utils/theatrical-messages.util';

@Component({
  selector: 'tava-theatrical-loader',
  standalone: true,
  templateUrl: './tava-theatrical-loader.component.html',
  styleUrl: './tava-theatrical-loader.component.scss',
})
export class TavaTheatricalLoaderComponent implements OnInit, AfterViewInit, OnDestroy {
  @Input() title = 'Preparando el escenario';
  @Input() context = 'loader';
  @Input() videoSrc = '/assets/videos/tava-loader.mp4?v=20260716';
  @ViewChild('loaderVideo') private videoRef?: ElementRef<HTMLVideoElement>;

  readonly currentMessage = signal('');
  readonly videoFailed = signal(false);
  private timer: ReturnType<typeof setInterval> | null = null;
  private playRetry: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
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
    if (!video || this.videoFailed()) return;
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
}
