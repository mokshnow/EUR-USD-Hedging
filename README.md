# Calculating the Most Optimial Currency Option to Hedge FX Risk:

EUR-USD-Hedging calculates the most optimal hedging strategy to protect from EUR/USD downside. The currency options are priced using the Garman-Kohlhagen Model. 

Choose the total EURC exposure, EUR/USD spot rate, FX IV, USD interest rate, EUR interest rate, put strike, and call strike. Then, the optimal strategy can be concluded from the parameters.

In this model, we test 4 different hedging strategies: 

  1.  _Unhedged_: Holding cash with no strategies
  2.  _Forward Contract_: Exchanging EUR for USD with another party at pre-determined conditions (requires no premium)
  3.  _Protective Put_: Holding cash while buying a put to sell the cash at a pre-determined price (requires premium for put)
  4.  _Collar_: Buy a put, and sell a call. Protects from downisde, but caps upside (recieve premium)


https://eur-usd-hedging.streamlit.app/
