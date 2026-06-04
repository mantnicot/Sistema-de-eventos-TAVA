import { Component, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { ApiService } from '../../core/services/api.service';

interface Kpis {
  eventos_activos: number;
  boletas_vendidas: number;
  ingresos: number;
  asistentes: number;
  conversion_porcentaje: number;
}

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './admin-dashboard.component.html',
  styleUrl: './admin-dashboard.component.scss',
})
export class AdminDashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly kpis = signal<Kpis | null>(null);

  ngOnInit(): void {
    this.api.get<Kpis>('/dashboard/kpis').subscribe({
      next: (k) => this.kpis.set(k),
      error: () => this.kpis.set(null),
    });
  }
}
