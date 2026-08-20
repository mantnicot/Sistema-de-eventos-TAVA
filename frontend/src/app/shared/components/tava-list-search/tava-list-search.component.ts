import { Component, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'tava-list-search',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './tava-list-search.component.html',
  styleUrl: './tava-list-search.component.scss',
})
export class TavaListSearchComponent {
  readonly query = input('');
  readonly placeholder = input('Buscar…');
  readonly hint = input('');
  readonly shown = input<number | null>(null);
  readonly total = input<number | null>(null);
  readonly queryChange = output<string>();

  onQuery(value: string): void {
    this.queryChange.emit(value ?? '');
  }
}
