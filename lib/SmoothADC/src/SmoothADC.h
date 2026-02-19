/*!\file SmoothADC.h
** \author SMFSW
** \date 2017/11/21
** \copyright GNU LESSER GENERAL PUBLIC LICENSE (c) 2017, SMFSW
** \brief Get ADC to return averaged values
**
** Local copy patched for ESP32 toolchains:
** - Use Arduino's `unsigned long` tick type for `micros()`/`millis()` compatibility
** - Avoid Arduino `String` usage in debug helper
**/

#ifndef SmoothADC_h
#define SmoothADC_h

#include <Arduino.h>
#include <stdint.h>

//#define DEBUG

#define DEF_NB_ACQ 4U //!< Number of acquisitions (specifies also size of tab)

/*!\enum tick_base
** \brief Tick resolution enum
**/
typedef enum tick_base {
  TB_US = 0, //!< us tick resolution
  TB_MS       //!< ms tick resolution
} tick_base;

/*!\struct SmoothADCAcq_t
** \brief SmoothADC handling struct
**/
typedef struct {
  uint16_t ADCTab[DEF_NB_ACQ]; //!< Acquisition tab
  uint16_t Average;            //!< Averaged value
  uint8_t NumAcq;              //!< Index of acquisition (number of Acq valid on MSB)
} SmoothADCAcq_t;

typedef SmoothADCAcq_t ADCId; //!< Alias name for Acquisition struct

/*! \class SmoothADC SmoothADC.h
** \brief class containing the required methods for ADC averaging
**/
class SmoothADC {
private:
  // consts
  uint16_t ADCPin;               //!< ACD Pin used
  unsigned long AcqPeriod;       //!< Acquisition Period
  tick_base Resolution;          //!< Tick resolution
  unsigned long (*get_tick)(void); //!< Time base function pointer

  // working vars
  ADCId ADCChannel;              //!< Acquisition struct
  unsigned long MemTimeAcq;      //!< Last Acquisition time
  bool En;                       //!< Module enabled/disable

  bool TestAcqRate(void);
  void Filtering(void);

public:
  void init(const uint16_t Pin, const tick_base Res, const unsigned long Period);
  void serviceADCPin(void);
  void dbgInfo(void);
  uint16_t getADCVal(void);

  inline void setPin(const uint16_t Pin) __attribute__((always_inline)) { ADCPin = Pin; }

  inline void setResolution(const tick_base Res) __attribute__((always_inline)) {
    Resolution = Res;
    get_tick = (Resolution == TB_US) ? micros : millis;
  }

  inline void setPeriod(const unsigned long Period) __attribute__((always_inline)) { AcqPeriod = Period; }

  inline uint16_t getPin(void) __attribute__((always_inline)) { return ADCPin; }
  inline tick_base getResolution(void) __attribute__((always_inline)) { return Resolution; }
  inline unsigned long getPeriod(void) __attribute__((always_inline)) { return AcqPeriod; }

  inline void enable(void) __attribute__((always_inline)) {
    En = true;
    SmoothADC::init(ADCPin, Resolution, AcqPeriod); // Reinit with same Pin, Resolution & Period
  }

  inline void disable(void) __attribute__((always_inline)) { En = false; }
  inline bool isEnabled(void) __attribute__((always_inline)) { return En; }
  inline bool isDisabled(void) __attribute__((always_inline)) { return (En ? false : true); }
};

#endif /* SmoothADC_h */

