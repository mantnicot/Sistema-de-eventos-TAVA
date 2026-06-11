import { Component, Input, OnDestroy, OnInit, signal } from '@angular/core';
import { randomTheatricalMessage } from '../../../core/utils/theatrical-messages.util';

@Component({
  selector: 'tava-theatrical-loader',
  standalone: true,
  templateUrl: './tava-theatrical-loader.component.html',
  styleUrl: './tava-theatrical-loader.component.scss',
})
export class TavaTheatricalLoaderComponent implements OnInit, OnDestroy {
  @Input() title = 'Preparando el escenario';
  @Input() context = 'loader';

  readonly currentMessage = signal('');
  private timer: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    this.rotate();
    this.timer = setInterval(() => this.rotate(), 3200);
  }

  ngOnDestroy(): void {
    if (this.timer) clearInterval(this.timer);
  }

  private rotate(): void {
    this.currentMessage.set(randomTheatricalMessage(this.context));
  }
}
