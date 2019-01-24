# -*- coding: utf-8 -*-

import threading as thrd

import numpy as np
import pandas as pd
from scipy.optimize import minimize

import matplotlib.pyplot as plt
from matplotlib import style

from equities import *
from fixed_income import getRiskFreeRate

style.use('ggplot')

class StockPortfolio:
	def __init__(self, stocks):
		self.__stocks = stocks

	def getStocks(self):
		return self.__stocks

	def addStock(self, stock):
		self.getStocks().append(stock)

	def getStocksWeights(self):
		return np.array([stock.getWeight() for stock in self.__stocks])

	def __calcCovMatrix(self):
		ret = {}

		for stock in self.__stocks:
			ret[stock.getQuote()] = stock.calcLogReturns()

		ret = pd.DataFrame(ret)
		cov_matrix = ret.cov()

		return ret, cov_matrix

	def calcMinVarAlloc(self, save = True, allow_short = True):
		n = len(self.__stocks)
		rets, cov_matrix = self.__calcCovMatrix()

		def __formulaCalculation():
			C_inv = np.linalg.inv(cov_matrix.values)
			e = np.ones(len(self.__stocks))

			weights = np.dot(e, C_inv) / np.dot(e, np.dot(C_inv, e))

			return weights

		def __optimizationSolution():
			minFun = lambda weights: np.sqrt(np.dot(weights.T, np.dot(rets.cov() * 252, weights)))

			cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
			bnds = tuple((0, 1) for _ in range(n))

			res = minimize(minFun, n * [1 / n], method = 'SLSQP', bounds = bnds, constraints = cons)
			weights = res.get('x')

			return weights

		if allow_short:
			weights =  __formulaCalculation()
		else:
			weights = __optimizationSolution()

		i = 0

		if save:
			for stock in self.__stocks:
				stock.setWeight(weights[i])
				i += 1

		return weights

	def calcMinVarLine(self, mv, save = True, allow_short = True):
		n = len(self.__stocks)
		rets, cov_matrix = self.__calcCovMatrix()

		def __formulaCalculation():
			m = rets.mean() * 252
			C_inv = np.linalg.inv(cov_matrix.values)
			e = np.ones(len(self.getStocks()))

			eC_invM = np.dot(np.dot(e, C_inv), m)
			mC_invM = np.dot(np.dot(m, C_inv), m)
			mC_invE = np.dot(np.dot(m, C_inv), e)
			eC_invE = np.dot(np.dot(e, C_inv), e)

			eC_inv = np.dot(e, C_inv)
			mC_inv = np.dot(m, C_inv)

			A = np.linalg.det([[1, eC_invM], [mv, mC_invM]])
			B = np.linalg.det([[eC_invE, 1], [mC_invE, mv]])
			C = np.linalg.det([[eC_invE, eC_invM], [mC_invE, mC_invM]])

			weights = (A * eC_inv + B * mC_inv) / C

			return weights

		def __optimizationSolution():
			minFun = lambda weights: np.sqrt(np.dot(weights.T, np.dot(rets.cov() * 252, weights)))

			cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1}, {'type': 'eq', 'fun': lambda x: np.sum(rets.mean() * x) * 252 - mv})
			bnds = tuple((0, 1) for _ in range(n))

			res = minimize(minFun, n * [1 / n], method = 'SLSQP', bounds = bnds, constraints = cons)
			weights = res.get('x')

			return weights

		if allow_short:
			weights =  __formulaCalculation()
		else:
			weights = __optimizationSolution()

		i = 0

		if save:
			for stock in self.getStocks():
				stock.setWeight(weights[i])
				i += 1

		return weights

	def maximizeSharpeRatio(self, rf, save = True, allow_short = False):
		n = len(self.__stocks)
		rets, cov_matrix = self.__calcCovMatrix()

		def __minFunc(weights):
			weights = np.array(weights)
			portExpRet = np.sum(rets.mean() * weights) * 252
			portStd = np.sqrt(np.dot(weights.T, np.dot(rets.cov() * 252, weights)))

			return -((portExpRet - rf) / portStd)

		cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})

		if allow_short:
			bnds = tuple((-1, 1) for _ in range(n))
		else:
			bnds = tuple((0, 1) for _ in range(n))

		res = minimize(__minFunc, n * [1 / n], method = 'SLSQP', bounds = bnds, constraints = cons)
		weights = res.get('x')

		i = 0

		if save:
			for stock in self.__stocks:
				stock.setWeight(weights[i])
				i += 1

		return weights

	def calcExpectedReturn(self):
		rets, cov_matrix = self.__calcCovMatrix()
		weights = self.getStocksWeights()

		exp_ret = np.dot(rets.mean(), weights) * 252

		return exp_ret

	def calcStandardDeviation(self):
		rets, cov_matrix = self.__calcCovMatrix()
		weights = self.getStocksWeights()

		std_dev = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights))) * np.sqrt(252)

		return std_dev

	def calcPerformance(self, *args):
		if len(args) == 2:
			rets = args[0]
			cov_matrix = args[1]
		elif len(args) == 3:
			rets = args[1]
			cov_matrix = args[2]
		else:
			rets, cov_matrix = self.__calcCovMatrix()

		weights = self.getStocksWeights()

		exRet = np.dot(rets.mean(), weights) * 252
		std = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights))) * np.sqrt(252)

		if len(args) == 1:
			rf = args[0]
			benchmark = Index('^GSPC')

			sharpeRatio = (exRet - rf) / std
			stocksBetas = np.array([s.calcBetaAlpha(benchmark)['beta'] for s in self.__stocks])
			stocksAlphas = np.array([s.calcBetaAlpha(benchmark)['alpha'] for s in self.__stocks])

			beta = stocksBetas.dot(weights)
			alpha = stocksAlphas.dot(weights)

			res = {'return': round(exRet, 5), 'std': round(std, 5), 'sharpe': round(sharpeRatio, 5), 'beta': round(beta, 5), 'alpha': round(alpha, 5)}
		else:
			res = {'return': round(exRet, 5), 'std': round(std, 5)}

		return res

	def printSummary(self, res):
		D = pd.DataFrame([self.getStocksWeights()], index = ['Allocation'])
		D.columns = [stock.getQuote() for stock in self.getStocks()]

		print('---------------------Portfolio Summary---------------------')
		print(D,'\n')
		print('Expected Return:', res['return'])
		print('Standard Deviation:', res['std'])

		if len(res) == 5:
			print('Sharpe Ratio:', res['sharpe'])
			print('Beta:', res['beta'])
			print('Alpha:', res['alpha'])

		print()

	def graphEfficientFrontier(self, graph = True):
		R = np.linspace(0.05, 0.35, 50)
		rets, cov_matrix = self.__calcCovMatrix()

		portExpRet = []
		portStd = []

		for i in R:
			self.calcMinVarLine(i, allow_short = True)
			res = self.calcPerformance(rets, cov_matrix)
			m = res['return']
			s = res['std']

			portExpRet.append(m)
			portStd.append(s)

		stockExpRet = []
		stockStd = []

		for stock in self.__stocks:
			stockExpRet.append(stock.calcExpReturn())
			stockStd.append(stock.calcStd())

		if graph:
			plt.plot(portStd, portExpRet, color = 'blue', linewidth = 2, label = "Efficient Frontier")
			plt.scatter(stockStd, stockExpRet, s = 30, color = 'red', label = "Asset")
			plt.ylabel("Expected return")
			plt.xlabel("Standard deviation")
			plt.title("Efficient Frontier")
			plt.legend(loc = 2)
			plt.show()

		return portExpRet, portStd

	def __generateRandomPortfolios(self, N):
		results = []

		for i in range(N):
			weights = np.random.random(len(self.__stocks))
			weights /= np.sum(weights)

			quotes = [s.getQuote() for s in self.__stocks]
			stocks = []
			j = 0

			for q in quotes:
				stocks.append(Stock(q, weights[j]))
				j += 1

			results.append(StockPortfolio(stocks))

		return results

	def graphSimulatedRandomProtfolios(self, N):
		simulated_portfolios = self.__generateRandomPortfolios(N)
		rets, cov_matrix = self.__calcCovMatrix()





		'''A = np.arange(0, N, N / 10)
		A = np.array([int(i) for i in A])

		S = [simulated_portfolios[A[i]:A[i + 1]] for i in range(len(A) - 1)]
		S.append(simulated_portfolios[A[-1]:])'''




		print(S)
		print(len(S[0]))
		print(len(S))




		'''rf = getRiskFreeRate()['10Y']

		M = []
		S = []
		i = 0

		for p in simulated_portfolios:
			res = p.calcPerformance(rets, cov_matrix)
			m = res['return']
			s = res['std']
			#print(i)

			#i += 1
			M.append(m)
			S.append(s)

		M = np.array(M)
		S = np.array(S)

		plt.scatter(S, M, s = 12, c = (M - rf) / S, alpha = 1, label = "Portfolio")
		plt.ylabel("Expected return")
		plt.xlabel("Standard deviation")
		plt.title("Simulated Random Portfolios")
		plt.colorbar(label = "Sharpe Ratio")
		plt.legend(loc = 2)
		plt.show()'''

class BondPortfolio:
	pass