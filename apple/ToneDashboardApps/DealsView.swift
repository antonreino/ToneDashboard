import SwiftUI

struct DealsView: View {
    @EnvironmentObject private var session: DashboardSession
    @State private var ean = ""
    @State private var savingProduct = false
    @State private var productMessage = ""
    @State private var productToRemove: TrackedProduct?
    @State private var confirmRemoval = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if let error = session.lastError { ErrorBanner(message: error) }
                if let deals = session.deals {
                    if !deals.available {
                        ErrorBanner(message: deals.error ?? "El bot de precios no está disponible")
                    }

                    DashboardPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Seguir otro producto por EAN").font(.headline)
                            TextField("EAN de 8 o 13 cifras", text: $ean)
                                .textFieldStyle(.roundedBorder)
                                .autocorrectionDisabled()
                            Button(savingProduct ? "Guardando…" : "Añadir producto") {
                                savingProduct = true
                                Task {
                                    if await session.addTrackedProduct(ean: ean.trimmingCharacters(in: .whitespacesAndNewlines)) {
                                        ean = ""
                                        productMessage = "Producto guardado. La primera lectura puede tardar unos minutos."
                                    }
                                    savingProduct = false
                                }
                            }
                            .disabled(savingProduct || ean.isEmpty)
                            Text(productMessage.isEmpty ? "Solo se agrupan coincidencias verificadas del EAN. Ofertas de menor a mayor precio." : productMessage)
                                .font(.caption).foregroundStyle(DashboardPalette.muted)
                        }
                    }
                    ForEach(deals.products ?? []) { product in
                        VStack(alignment: .trailing, spacing: 6) {
                        OfferFamilyCard(title: product.name, subtitle: product.family == "ean" || product.family == nil ? "EAN \(product.ean)" : "Seguimiento de ofertas",
                                        systemImage: product.family == "ean" || product.family == nil ? "barcode" : "gamecontroller.fill", accent: DashboardPalette.cyan,
                                        offers: deals.activeOffers.filter { product.family == "ean" || product.family == nil ? $0.ean == product.ean : $0.family == product.family })
                        Button("Eliminar producto", role: .destructive) {
                            productToRemove = product
                            confirmRemoval = true
                        }.disabled(savingProduct)
                        }
                    }
                    ForEach(deals.inactiveProducts ?? []) { product in
                        Button("Volver a seguir \(product.name)") {
                            savingProduct = true
                            Task {
                                _ = await session.restoreTrackedProduct(id: product.id)
                                savingProduct = false
                            }
                        }.disabled(savingProduct)
                    }

                    DashboardPanel {
                        VStack(alignment: .leading, spacing: 12) {
                            Label("Últimos avisos", systemImage: "bell.fill")
                                .font(.headline)
                                .foregroundStyle(DashboardPalette.text)
                            if deals.history.isEmpty {
                                Text("No hay avisos recientes.").foregroundStyle(DashboardPalette.muted)
                            } else {
                                ForEach(Array(deals.history.enumerated()), id: \.element.id) { index, item in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(item.body).foregroundStyle(DashboardPalette.text)
                                        Text(prettyDate(item.createdIso)).font(.caption).foregroundStyle(DashboardPalette.muted)
                                    }
                                    if index < deals.history.count - 1 {
                                        Divider().overlay(DashboardPalette.border)
                                    }
                                }
                            }
                        }
                    }
                    DashboardPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            Label("Estado de las fuentes", systemImage: "antenna.radiowaves.left.and.right").font(.headline)
                            if deals.events.isEmpty { Text("Sin eventos recientes.").foregroundStyle(DashboardPalette.muted) }
                            ForEach(deals.events) { event in
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        Text(event.name).bold()
                                        Spacer()
                                        StatusPill(text: event.level == "error" ? "Error" : "Recuperada", good: event.level != "error")
                                    }
                                    Text(event.detail)
                                    Text(prettyDate(event.createdIso)).font(.caption).foregroundStyle(DashboardPalette.muted)
                                }
                            }
                        }
                    }
                    DashboardPanel {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Registro del bot").font(.headline)
                            LogLineCountPicker()
                            Text(deals.log ?? "(vacío)")
                                .font(.system(.caption, design: .monospaced))
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                } else if session.lastError != nil {
                    ContentUnavailableView("No se pudieron cargar las ofertas", systemImage: "wifi.exclamationmark", description: Text("Comprueba la conexión y vuelve a actualizar."))
                } else {
                    ProgressView("Cargando ofertas…")
                        .tint(DashboardPalette.accent)
                        .foregroundStyle(DashboardPalette.text)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 80)
                }
            }
            .padding()
        }
        .confirmationDialog("¿Dejar de seguir este producto?", isPresented: $confirmRemoval, titleVisibility: .visible, presenting: productToRemove) { product in
            Button("Eliminar producto", role: .destructive) {
                savingProduct = true
                Task {
                    _ = await session.removeTrackedProduct(id: product.id)
                    savingProduct = false
                    productToRemove = nil
                }
            }
            Button("Cancelar", role: .cancel) { productToRemove = nil }
        } message: { product in
            Text("\(product.name). Dejarás de recibir avisos de este producto. Se conservará el historial.")
        }
        .background(DashboardBackground())
        .navigationTitle("Ofertas")
        .refreshable { await session.refreshAll() }
    }
}

private struct OfferFamilyCard: View {
    let title: String
    let subtitle: String
    let systemImage: String
    let accent: Color
    let offers: [Offer]

    var body: some View {
        DashboardPanel {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 10) {
                    Image(systemName: systemImage)
                        .font(.title2)
                        .foregroundStyle(accent)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(title).font(.title3.bold()).foregroundStyle(DashboardPalette.text)
                        Text(subtitle).font(.caption).foregroundStyle(DashboardPalette.muted)
                    }
                }

                if offers.isEmpty {
                    Text("No hay ofertas activas en este momento.")
                        .foregroundStyle(DashboardPalette.muted)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.vertical, 14)
                } else {
                    ForEach(Array(offers.sorted { ($0.price ?? Int.max) < ($1.price ?? Int.max) }.enumerated()), id: \.element.id) { index, offer in
                        VStack(alignment: .leading, spacing: 7) {
                            HStack(alignment: .top) {
                                Text(offer.title ?? "Sin título")
                                    .font(.headline)
                                    .foregroundStyle(DashboardPalette.text)
                                Spacer(minLength: 12)
                                Text(euroString(cents: offer.price))
                                    .font(.headline)
                                    .foregroundStyle(DashboardPalette.ok)
                            }
                            let seller = [offer.source, offer.seller].compactMap { $0 }.joined(separator: " · ")
                            if !seller.isEmpty {
                                Text(seller).font(.caption).foregroundStyle(DashboardPalette.muted)
                            }
                            Text("\(offerKindLabel(offer.kind)) · \(availabilityLabel(offer.availability))")
                                .font(.caption).foregroundStyle(DashboardPalette.muted)
                            Text(offer.shipping.map { "Envío: \(euroString(cents: $0))" } ?? "Envío por confirmar")
                                .font(.caption).foregroundStyle(DashboardPalette.muted)
                            Text("Última lectura: \(prettyDate(offer.seenIso))")
                                .font(.caption).foregroundStyle(DashboardPalette.muted)
                            if let url = safeOfferURL(offer.url) {
                                Link(destination: url) {
                                    Label("Abrir oferta", systemImage: "arrow.up.right.square")
                                        .font(.subheadline.weight(.semibold))
                                        .foregroundStyle(accent)
                                }
                            }
                        }
                        if index < offers.count - 1 {
                            Divider().overlay(DashboardPalette.border)
                        }
                    }
                }
            }
        }
    }
}
