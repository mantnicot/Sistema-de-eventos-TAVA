import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SlicePipe } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';
import { ApiService } from '../../core/services/api.service';

interface Ticket {
  id: string;
  event_id: string;
  qr_token: string;
  is_used: boolean;
}

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [RouterLink, SlicePipe],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  readonly tickets = signal<Ticket[]>([]);

  ngOnInit(): void {
    if (this.auth.isLoggedIn()) {
      this.api.get<Ticket[]>('/tickets/mine').subscribe({
        next: (t) => this.tickets.set(t),
        error: () => this.tickets.set([]),
      });
    }
  }
}
