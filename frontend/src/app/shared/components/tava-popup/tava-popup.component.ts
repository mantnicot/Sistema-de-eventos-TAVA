import { Component, effect, inject, OnDestroy, signal } from '@angular/core';
import { NotificationService } from '../../../core/services/notification.service';
import { randomPopupPhrase } from '../../../core/utils/theatrical-messages.util';
import { TavaTheatricalLoaderComponent } from '../tava-theatrical-loader/tava-theatrical-loader.component';

@Component({
  selector: 'tava-popup',
  standalone: true,
  imports: [TavaTheatricalLoaderComponent],
  templateUrl: './tava-popup.component.html',
  styleUrl: './tava-popup.component.scss',
})
export class TavaPopupComponent implements OnDestroy {
  readonly notify = inject(NotificationService);
  readonly rotatingPhrase = signal('');
  readonly roseSlots = Array.from({ length: 28 }, (_, i) => i);
  readonly petalSlots = Array.from({ length: 16 }, (_, i) => i);

  private phraseTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    effect(() => {
      const visible = !!this.notify.state()?.visible;
      this.clearPhraseTimer();
      if (visible) {
        this.rotatingPhrase.set(randomPopupPhrase());
        this.phraseTimer = setInterval(() => {
          this.rotatingPhrase.set(randomPopupPhrase());
        }, 5000);
      }
    });
  }

  roseSize(i: number): string {
    const sizes = ['1rem', '1.2rem', '1.45rem', '1.1rem', '1.6rem', '0.95rem'];
    return sizes[i % sizes.length];
  }

  ngOnDestroy(): void {
    this.clearPhraseTimer();
  }

  confirm(): void {
    const s = this.notify.state();
    s?.onConfirm?.();
    this.notify.hide();
  }

  cancel(): void {
    this.notify.hide();
  }

  private clearPhraseTimer(): void {
    if (this.phraseTimer) {
      clearInterval(this.phraseTimer);
      this.phraseTimer = null;
    }
  }
}
