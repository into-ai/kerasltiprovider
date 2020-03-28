package main

import (
	"fmt"
	"math"
	"net/http"
	"os"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis"
	log "github.com/sirupsen/logrus"
	"github.com/urfave/cli/v2"
)

var db *redis.Client

type validationData struct {
	Predicted int
	Hash      string
	Input     string
}

type validationHashTable map[string]validationData

var assignments map[string]validationHashTable
var assignmentKeys map[string][]string

func loadValidationSet(assignmentID string) error {
	// Check if has key before making a database request
	if _, ok := assignments[assignmentID]; ok {
		return nil
	}

	var cursor uint64
	keys := []string{}

	vht := make(map[string]validationData)
	query := fmt.Sprintf("%s:*", assignmentID)

	log.Debugf("Querying inputs with keys: %s", query)
	for {
		var batchKeys []string
		var err error
		batchKeys, cursor, err = db.Scan(cursor, query, 10).Result()
		if err != nil {
			return err
		}
		keys = append(keys, batchKeys...)
		if cursor == 0 {
			break
		}
	}

	if len(keys) < 1 {
		return fmt.Errorf("Cannot find assignment with ID %s", assignmentID)
	}

	log.Debugf("Found %d input data entries", len(keys))

	for _, key := range keys {
		values, err := db.HMGet(key, "predicted", "hash", "input").Result()
		if err != nil {
			log.Error(err)
			continue
		}

		predicted, err := strconv.Atoi(values[0].(string))
		if err != nil {
			log.Error(err)
			continue
		}
		hash := values[1].(string)
		vht[hash] = validationData{Predicted: predicted, Hash: hash}
	}

	assignments[assignmentID] = vht
	assignmentKeys[assignmentID] = keys
	return nil
}

func roundToDigits(x float64, digits int) float64 {
	ndigits := math.Pow(10, float64(digits))
	return math.Round(x*ndigits) / ndigits
}

func setupRouter() *gin.Engine {
	r := gin.Default()

	r.GET("/assignment/:assignmentID/size", func(c *gin.Context) {
		assignmentID := c.Params.ByName("assignmentID")
		loadValidationSet(assignmentID)
		size := len(assignmentKeys[assignmentID])
		c.JSON(http.StatusOK, gin.H{"size": size})
	})

	r.GET("/assignment/:assignmentID/inputs/:inputID", func(c *gin.Context) {
		assignmentID := c.Params.ByName("assignmentID")
		inputID, err := strconv.Atoi(c.Params.ByName("inputID"))
		if err != nil {
			log.Warn("inputID must be an integer")
			c.JSON(http.StatusBadRequest, gin.H{"error": "inputID must be an integer", "success": false})
			return
		}
		loadValidationSet(assignmentID)
		if keys, ok := assignmentKeys[assignmentID]; ok && inputID < len(keys) {
			key := keys[inputID]
			values, err := db.HMGet(key, "hash", "input").Result()
			if err != nil {
				log.Error(err)
			}
			hash := values[0]
			input := values[1]
			content := fmt.Sprintf(`{"predict": [{"hash": "%s", "matrix": %s}]}`, hash, input)
			c.Data(http.StatusOK, "application/json", []byte(content))
			return
		}

		c.JSON(http.StatusBadRequest, gin.H{"error": "unknown assignment or out of range", "success": false})
	})

	r.POST("/internal/:assignmentID/validate", func(c *gin.Context) {
		assignmentID := c.Params.ByName("assignmentID")
		loadValidationSet(assignmentID)
		var predictions map[string]int
		c.BindJSON(&predictions)
		log.Debugf("Predictions for %s: %v", assignmentID, predictions)

		assignmentData, ok := assignments[assignmentID]
		if !ok {
			log.Warnf("unknown assignment: %s", assignmentID)
			c.JSON(http.StatusBadRequest, gin.H{"error": "unknown assignment", "success": false})
			return
		}

		expectedPredictionsNum := len(assignmentData)
		if len(predictions) != expectedPredictionsNum {
			log.Warnf("Expected %d predictions, but got %d", expectedPredictionsNum, len(predictions))
			c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("Expected %d predictions", expectedPredictionsNum), "success": false})
			return
		}

		numCorrect := 0
		for hash, prediction := range predictions {
			if expected, ok := assignmentData[hash]; ok && float64(expected.Predicted) == float64(prediction) {
				numCorrect++
			}
		}

		accuracy := roundToDigits(float64(numCorrect)/float64(expectedPredictionsNum), 2)
		log.Infof("Grading %f", accuracy)
		c.JSON(http.StatusOK, gin.H{"accuracy": accuracy})
	})

	return r
}

func serve(c *cli.Context) error {
	// Prepare data
	assignments = make(map[string]validationHashTable)
	assignmentKeys = make(map[string][]string)

	// Connect to redis database
	db = redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", c.String("redis-host"), c.Int("redis-port")),
		Password: c.String("redis-password"),
		DB:       c.Int("redis-db"),
	})

	if c.Bool("production") {
		gin.SetMode(gin.ReleaseMode)
	}

	r := setupRouter()
	r.Run(fmt.Sprintf(":%d", c.Int("port")))
	return nil
}

func run(args []string) error {
	app := &cli.App{
		Flags: []cli.Flag{
			&cli.StringFlag{
				Name:    "redis-host",
				EnvVars: []string{"REDIS_HOST"},
				Value:   "localhost",
				Usage:   "redis host",
			},
			&cli.IntFlag{
				Name:    "redis-port",
				EnvVars: []string{"REDIS_PORT"},
				Value:   6379,
				Usage:   "redis port",
			},
			&cli.IntFlag{
				Name:    "redis-db",
				EnvVars: []string{"REDIS_DB"},
				Value:   1,
				Usage:   "redis db",
			},
			&cli.StringFlag{
				Name:    "redis-password",
				EnvVars: []string{"REDIS_PASSWORD"},
				Value:   "",
				Usage:   "redis password",
			},
			&cli.IntFlag{
				Name:    "port",
				EnvVars: []string{"PORT"},
				Value:   9000,
				Usage:   "Service port",
			},
			&cli.BoolFlag{
				Name:    "production",
				EnvVars: []string{"PRODUCTION"},
				Value:   true,
				Usage:   "Enable production mode",
			},
		},
		Action: func(c *cli.Context) error {
			err := serve(c)
			return err
		},
	}
	return app.Run(args)
}

func main() {
	err := run(os.Args)
	if err != nil {
		log.Fatal(err)
	}
}
