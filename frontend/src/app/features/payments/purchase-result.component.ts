import { Component, inject, OnDestroy, OnInit } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { NotificationService } from '../../core/services/notification.service';

interface OrderStatus {
  order_id: string;
  payment_status: string;
  event_name?: string;
  ticket_type?: string;
  total?: number;
  tickets_ready?: boolean;
  pdf_url?: string | null;
  message?: string;
}

@Component({
  selector: 'app-purchase-result',
  standalone: true,
  imports: [RouterLink, DecimalPipe],
  templateUrl: './purchase-result.component.html',
  styleUrl: './purchase-result.component.scss',
})
export class PurchaseResultComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly notify = inject(NotificationService);
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private confirmAttempted = false;
  private notifiedReady = false;

  orderId = '';
  status: OrderStatus | null = null;
  loading = true;
  error = '';

  ngOnInit(): void {
    this.orderId = this.route.snapshot.queryParamMap.get('order_id') ?? '';
    const wompiTxId = this.route.snapshot.queryParamMap.get('id');
    if (!this.orderId) {
      this.loading = false;
      this.error = 'No se encontró la orden de compra.';
      return;
    }
    this.refresh(wompiTxId);
    this.pollTimer = setInterval(() => this.refresh(wompiTxId), 1500);
  }

  ngOnDestroy(): void {
    if (this.pollTimer) clearInterval(this.pollTimer);
  }

  private refresh(wompiTxId: string | null): void {
    this.api.get<OrderStatus>(`/payments/orders/${this.orderId}/status`).subscribe({
      next: (data) => {
        this.status = data;
        this.loading = false;
        if (this.finishIfReady(data)) {
          return;
        }
        if (data.payment_status === 'pendiente' && wompiTxId && !this.confirmAttempted) {
          this.confirmAttempted = true;
          this.api
            .post<OrderStatus>(`/payments/wompi/confirm/${this.orderId}?transaction_id=${encodeURIComponent(wompiTxId)}`, {})
            .subscribe({
              next: (confirmed) => {
                this.status = confirmed;
                this.loading = false;
                this.finishIfReady(confirmed);
              },
            });
        }
        if (data.payment_status === 'rechazado' && this.pollTimer) {
          clearInterval(this.pollTimer);
          this.pollTimer = null;
        }
      },
      error: () => {
        this.loading = false;
        this.error = 'No pudimos consultar el estado del pago. Espera unos segundos y vuelve a intentar.';
      },
    });
  }

  private finishIfReady(data: OrderStatus): boolean {
    if (!data.tickets_ready) return false;
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    if (!this.notifiedReady) {
      this.notifiedReady = true;
      this.notify.success('Pago confirmado', 'Tus boletas ya están listas. También enviaremos el PDF a tu correo.');
    }
    return true;
  }
}
