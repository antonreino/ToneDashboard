import SwiftUI

struct DealsView: View {
    @EnvironmentObject private var session: DashboardSession

    private var ps5Offers: [Offer] {
        (session.deals?.activeOffers ?? []).filter { ($0.family ?? "").lowercased() != "switch2" }
    }

    private var switchOffers: [Offer] {
        (session.deals?.activeOffers ?? []).filter { ($0.family ?? "").lowercased() == "switch2" }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if let deals = session.deals {
                    if !deals.available {
                        ErrorBanner(message: deals.error ?? "El bot de precios no está disponible")
                    }

                    ViewThatFits(in: .horizontal) {
                        HStack(alignment: .top, spacing: 16) {
                            OfferFamilyCard(
                                title: "PlayStation 5",
                                subtitle: "Ofertas de PS5",
                                systemImage: "gamecontroller.fill",
                                accent: DashboardPalette.accent,
                                offers: ps5Offers
                            )
                            .frame(minWidth: 320, maxWidth: .infinity, alignment: .topLeading)

                            OfferFamilyCard(
                                title: "Nintendo Switch",
                                subtitle: "Ofertas de Switch",
                                systemImage: "gamecontroller",
                                accent: DashboardPalette.cyan,
                                offers: switchOffers
                            )
                            .frame(minWidth: 320, maxWidth: .infinity, alignment: .topLeading)
                        }
                        .frame(maxWidth: .infinity, alignment: .topLeading)

                        VStack(alignment: .leading, spacing: 16) {
                            OfferFamilyCard(
                                title: "PlayStation 5",
                                subtitle: "Ofertas de PS5",
                                systemImage: "gamecontroller.fill",
                                accent: DashboardPalette.accent,
                                offers: ps5Offers
                            )
                            .frame(maxWidth: .infinity, alignment: .topLeading)

                            OfferFamilyCard(
                                title: "Nintendo Switch",
                                subtitle: "Ofertas de Switch",
                                systemImage: "gamecontroller",
                                accent: DashboardPalette.cyan,
                                offers: switchOffers
                            )
                            .frame(maxWidth: .infinity, alignment: .topLeading)
                        }
                    }

                    DashboardPanel {
                        VStack(alignment: .leading, spacing: 12) {
                            Label("Últimos avisos", systemImage: "bell.fill")
                                .font(.headline)
                                .foregroundStyle(DashboardPalette.text)
                            if deals.history.isEmpty {
                                Text("No hay avisos recientes.").foregroundStyle(DashboardPalette.muted)
                            } else {
                                ForEach(Array(deals.history.prefix(40).enumerated()), id: \.element.id) { index, item in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(item.body).foregroundStyle(DashboardPalette.text)
                                        Text(prettyDate(item.createdIso)).font(.caption).foregroundStyle(DashboardPalette.muted)
                                    }
                                    if index < min(deals.history.count, 40) - 1 {
                                        Divider().overlay(DashboardPalette.border)
                                    }
                                }
                            }
                        }
                    }
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
                    ForEach(Array(offers.enumerated()), id: \.element.id) { index, offer in
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
                            if let raw = offer.url, let url = URL(string: raw) {
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
