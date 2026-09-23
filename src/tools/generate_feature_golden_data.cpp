// One-time deterministic fixture generator. Native C++ only; seed=42.
// Build target: generate_feature_golden_data. Run from repository root.
#include "ml/FeatureEngineer.hpp"
#include <Eigen/Dense>
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>
#include <random>
#include <vector>

using json = nlohmann::json;
using ml::OrderBookFeatures;
using Vec = std::vector<double>;
constexpr int kDim = 353;

static double log1p_pos(double x) { return std::log1p(std::max(0.0, x)); }
static double log_pos(double x) { return x > 0 ? std::log(x) : 0.0; }
static Vec base(const OrderBookFeatures& f) {
  double bl=log1p_pos(f.bid_volume), al=log1p_pos(f.ask_volume), wl=log1p_pos(f.wall_size);
  double dl=log1p_pos(f.order_book_depth), ml=log_pos(f.mid_price), vl=log_pos(f.volume_weighted_price);
  Vec x={f.bid_ask_imbalance,f.spread_percent,ml,bl,al,dl,f.large_bid_wall?1.:0.,f.large_ask_wall?1.:0.,wl,vl,f.price_momentum,f.volatility,
    bl/(al+1e-8),f.spread_percent/(f.mid_price+1e-8),wl/(bl+al+1e-8),f.price_momentum/(f.volatility+1e-8),
    log1p_pos(f.volume_24h),log1p_pos(f.volume_30d),f.low_24h>0?(f.high_24h-f.low_24h)/f.low_24h:0.,f.high_24h>f.low_24h?(f.mid_price-f.low_24h)/(f.high_24h-f.low_24h):.5,
    std::tanh(f.price_momentum/5.),std::clamp(f.volatility/10.,0.,1.),std::tanh((f.price_momentum/(f.volatility+1e-8))/2.),ml-vl,
    f.mid_price>0?(4.*f.volatility)/f.mid_price:0.,f.volatility};
  for(double& v:x) if(!std::isfinite(v)) v=std::signbit(v)?-1e9:1e9;
  return x;
}
static Vec engineered(const std::vector<Vec>& hist, const Vec& cur) {
  Vec out=cur; const int ws[]={5,10,20,50,90,200};
  for(int w:ws){ int start=std::max(0,(int)hist.size()-w), n=(int)hist.size()-start; Vec mean(26), sd(26);
    for(int i=start;i<(int)hist.size();++i) for(int j=0;j<26;++j){ double d=hist[i][j]-(i?hist[i-1][j]:hist[i][j]); mean[j]+=d; }
    for(double&v:mean)v/=std::max(1,n);
    if(n>1) for(int i=start;i<(int)hist.size();++i) for(int j=0;j<26;++j){ double d=hist[i][j]-(i?hist[i-1][j]:hist[i][j]); sd[j]+=(d-mean[j])*(d-mean[j]); }
    if(n>1) for(double&v:sd)v=std::sqrt(v/(n-1));
    out.insert(out.end(),mean.begin(),mean.end()); out.insert(out.end(),sd.begin(),sd.end());
  }
  for(int i=0;i<5;++i) for(int j=i;j<5;++j) out.push_back(cur[i]*cur[j]);
  return out;
}
static OrderBookFeatures sample(std::mt19937& g,int i,double step) {
  std::normal_distribution<double> n(0,1); std::uniform_real_distribution<double> u(0,1);
  double mid=10000.+i*step+n(g)*(step==1?10.:5.); OrderBookFeatures f{}; f.timestamp=1700000000+i*60; f.symbol="BTC-USD";
  f.bid_ask_imbalance=n(g); f.spread_percent=.001+u(g)*.001; f.mid_price=mid; f.bid_volume=1+u(g)*10; f.ask_volume=1+u(g)*10; f.order_book_depth=5;
  f.large_bid_wall=(u(g)<.5); f.large_ask_wall=(u(g)<.5); f.wall_size=10+u(g)*50; f.volume_weighted_price=mid+n(g)*2;
  f.price_momentum=n(g)*.1; f.volatility=.02+u(g)*.01; f.volume_24h=1e6; f.volume_30d=3e7; f.high_24h=mid*1.02; f.low_24h=mid*.98; f.prev_win_probability=.5; f.prev_expected_return=.01; f.prev_confidence=.8; return f;
}
int main(){
  std::mt19937 g(42); std::vector<Vec> rows; std::vector<Vec> bases; std::vector<Vec> hist;
  for(int i=0;i<300;++i){ auto f=sample(g,i,1.); auto b=base(f); bases.push_back(b); hist.push_back(b); rows.push_back(engineered(hist,b)); }
  Eigen::MatrixXd X(300,kDim); for(int i=0;i<300;++i) for(int j=0;j<kDim;++j) X(i,j)=rows[i][j];
  Vec im(kDim),mean(kDim),scale(kDim); for(int j=0;j<kDim;++j){ im[j]=0.; for(const auto& r:rows) im[j]+=r[j]; im[j]/=300.; }
  for(int j=0;j<kDim;++j){ mean[j]=X.col(j).mean(); double s=0; for(int i=0;i<300;++i) s+=(X(i,j)-mean[j])*(X(i,j)-mean[j]); scale[j]=std::sqrt(s/300); if(scale[j]<1e-12) scale[j]=1.; }
  Eigen::MatrixXd Z=X; for(int i=0;i<300;++i) for(int j=0;j<kDim;++j) Z(i,j)=(X(i,j)-mean[j])/scale[j];
  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> es((Z.transpose()*Z)/299.); Eigen::MatrixXd comp(10,kDim); for(int k=0;k<10;++k) comp.row(k)=es.eigenvectors().col(kDim-1-k).transpose();
  json components=json::array(); for(int i=0;i<10;++i) components.push_back(std::vector<double>(comp.row(i).data(),comp.row(i).data()+kDim));
  json p={{"imputer",{{"statistics",im}}},{"scaler",{{"mean",mean},{"scale",scale}}},{"pca",{{"components",components},{"mean",std::vector<double>(kDim,0.)}}}};
  std::ofstream("data/cpp_assets/feature_params.json")<<p.dump(2)<<'\n';
  ml::FeatureEngineer fe; fe.load_parameters("data/cpp_assets/feature_params.json"); json golden=json::array(); g.seed(42); for(int i=0;i<10;++i){auto f=sample(g,i,10.); auto pca=fe.preprocess(f); golden.push_back({{"raw",{{"bid_ask_imbalance",f.bid_ask_imbalance},{"spread_percent",f.spread_percent},{"mid_price",f.mid_price},{"bid_volume",f.bid_volume},{"ask_volume",f.ask_volume},{"order_book_depth",f.order_book_depth},{"large_bid_wall",f.large_bid_wall},{"large_ask_wall",f.large_ask_wall},{"wall_size",f.wall_size},{"volume_weighted_price",f.volume_weighted_price},{"price_momentum",f.price_momentum},{"volatility",f.volatility},{"volume_24h",f.volume_24h},{"volume_30d",f.volume_30d},{"high_24h",f.high_24h},{"low_24h",f.low_24h},{"prev_win_probability",f.prev_win_probability},{"prev_expected_return",f.prev_expected_return},{"prev_confidence",f.prev_confidence}}},{"pca",pca}});}
  std::ofstream("data/cpp_assets/golden_features.json")<<golden.dump(2)<<'\n'; std::cout<<"Generated 353-dim params and 10 golden samples (seed=42)\n"; }
